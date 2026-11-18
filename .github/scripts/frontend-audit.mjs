import { spawnSync } from 'node:child_process'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const advisory = 'GHSA-fc5q-39xc-vjpf'
const packageName = 'picomatch'
const approvedVersion = '4.0.7'
const expires = '2026-12-18T00:00:00Z'
const severityOrder = ['info', 'low', 'moderate', 'high', 'critical']
const blocking = severity => severityOrder.indexOf(severity) >= 2
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const isPicomatch = (location, name) =>
  name === packageName || /(?:^|\/)node_modules\/picomatch$/.test(location)

function parseNpmResult(label, result) {
  if (result.error || result.signal || ![0, 1].includes(result.status)) {
    throw new Error(`${label} did not complete successfully`)
  }
  try {
    return JSON.parse(result.stdout)
  } catch {
    throw new Error(`${label} did not produce valid JSON`)
  }
}

function readAudit(label, result) {
  const report = parseNpmResult(label, result)
  if (!isObject(report) || 'error' in report || report.auditReportVersion !== 2 ||
      !isObject(report.vulnerabilities) || !isObject(report.metadata?.vulnerabilities)) {
    throw new Error(`${label} returned an error or an unsupported report`)
  }

  const entries = new Map(Object.entries(report.vulnerabilities))
  const counts = Object.fromEntries(severityOrder.map(severity => [severity, 0]))
  for (const [name, entry] of entries) {
    if (!isObject(entry) || name !== entry.name || !severityOrder.includes(entry.severity) ||
        !Array.isArray(entry.nodes) || !entry.nodes.length ||
        !entry.nodes.every(node => typeof node === 'string' && node.startsWith('node_modules/')) ||
        !Array.isArray(entry.via) || !entry.via.length) {
      throw new Error(`${label} has an invalid vulnerability record`)
    }
    counts[entry.severity]++
    for (const cause of entry.via) {
      if (typeof cause === 'string' && entries.has(cause)) continue
      if (isObject(cause) && cause.name === name && cause.dependency === name &&
          typeof cause.url === 'string' && cause.url.length &&
          severityOrder.includes(cause.severity) &&
          severityOrder.indexOf(cause.severity) <= severityOrder.indexOf(entry.severity)) continue
      throw new Error(`${label} has an unresolved or unsupported vulnerability cause`)
    }
  }
  const metadata = report.metadata.vulnerabilities
  const expectedStatus = counts.moderate || counts.high || counts.critical ? 1 : 0
  if (metadata.total !== entries.size || result.status !== expectedStatus ||
      severityOrder.some(severity => metadata[severity] !== counts[severity])) {
    throw new Error(`${label} exit status or vulnerability counts disagree with the report`)
  }
  return entries
}

// Walk from advisory-bearing entries to their dependents. The visited set also
// handles cycles such as Vitest and its optional coverage provider.
function dependentsOf(parents, roots) {
  const visited = new Set(roots)
  for (const name of visited) {
    for (const parent of parents.get(name)) visited.add(parent)
  }
  return visited
}

function traceAdvisories(entries) {
  const parents = new Map([...entries.keys()].map(name => [name, new Set()]))
  const approved = new Set()
  const other = new Set()
  for (const [name, entry] of entries) {
    for (const cause of entry.via) {
      if (typeof cause === 'string') {
        parents.get(cause).add(name)
      } else if (name === packageName && cause.severity === 'high' &&
                 cause.url === `https://github.com/advisories/${advisory}`) {
        approved.add(name)
      } else {
        other.add(name)
      }
    }
  }
  const chain = dependentsOf(parents, approved)
  const otherChain = dependentsOf(parents, other)
  for (const [name, entry] of entries) {
    if (!chain.has(name) && !otherChain.has(name)) {
      throw new Error(`Unresolved npm advisory chain for ${name}`)
    }
    if (blocking(entry.severity) && (!chain.has(name) || otherChain.has(name))) {
      throw new Error(`Blocking npm vulnerability outside the exception for ${name}`)
    }
  }
  return chain
}

export function evaluateAudits({ full, production, lock, installed }, now = Date.now()) {
  const fullEntries = readAudit('Full npm audit', full)
  const prodEntries = readAudit('Production npm audit', production)
  if (production.status !== 0) throw new Error('Production npm audit found a blocking vulnerability')
  traceAdvisories(prodEntries)

  const packages = lock?.packages
  const root = packages?.['']
  if (lock?.lockfileVersion !== 3 || !isObject(packages) ||
      typeof root?.name !== 'string' || typeof root?.version !== 'string' || !Array.isArray(installed)) {
    throw new Error('Unsupported npm lockfile or installed dependency tree')
  }
  const actual = new Map()
  for (const node of installed) {
    if (!isObject(node) || typeof node.location !== 'string' || actual.has(node.location) ||
        typeof node.name !== 'string' || typeof node.version !== 'string' || typeof node.dev !== 'boolean') {
      throw new Error('Invalid installed npm dependency record')
    }
    actual.set(node.location, node)
  }
  if (actual.get('')?.name !== root.name || actual.get('')?.version !== root.version || actual.get('')?.dev !== false) {
    throw new Error('Installed npm dependency tree does not match the lockfile root')
  }
  for (const tree of [Object.entries(packages), actual]) {
    for (const [location, node] of tree) {
      if (!isObject(node)) throw new Error('Invalid npm dependency record')
      if (isPicomatch(location, node.name) && node.dev !== true) {
        throw new Error('picomatch is present outside the frontend dev dependency tree')
      }
    }
  }

  const chain = traceAdvisories(fullEntries)
  if (!chain.size) return null
  if (!Number.isFinite(now) || now >= Date.parse(expires)) {
    throw new Error(`The ${advisory} security exception expired at ${expires}`)
  }
  for (const name of chain) {
    for (const location of fullEntries.get(name).nodes) {
      const locked = Object.hasOwn(packages, location) ? packages[location] : undefined
      const node = actual.get(location)
      if (locked?.dev !== true || node?.dev !== true || node.name !== name ||
          node.version !== locked.version || (name === packageName && node.version !== approvedVersion)) {
        throw new Error(`Cannot verify dev-only scope and approved version for ${name} at ${location}`)
      }
    }
  }
  return `SECURITY EXCEPTION ACTIVE | Advisory: ${advisory} | Package: ${packageName}@${approvedVersion} | ` +
    `Scope: devDependencies only | Reason: no official patched release | Expires: ${expires} | ` +
    'All other Moderate and higher vulnerabilities remain blocking.'
}

function run(reportDirectory) {
  if (!reportDirectory) throw new Error('Pass a directory for the raw JSON audit reports')
  mkdirSync(reportDirectory, { recursive: true })
  const cwd = fileURLToPath(new URL('../../', import.meta.url))
  const npm = (...args) => spawnSync('npm', ['--prefix', 'frontend', ...args], {
    cwd, encoding: 'utf8', maxBuffer: 16 * 1024 * 1024,
  })
  const audit = (file, scope) => {
    const result = npm('audit', '--audit-level=moderate', '--json', ...scope)
    writeFileSync(join(reportDirectory, file), result.stdout ?? '')
    return result
  }
  const full = audit('full.json', ['--include=dev', '--include=optional', '--include=peer'])
  const production = audit('production.json', ['--omit=dev', '--include=optional', '--include=peer'])
  const tree = npm('query', ':root, *', '--package-lock-only=false')
  if (tree.status !== 0) throw new Error('Could not read the installed frontend dependency tree')
  const installed = parseNpmResult('Installed frontend dependency query', tree)
  const lock = JSON.parse(readFileSync(join(cwd, 'frontend/package-lock.json'), 'utf8'))
  const warning = evaluateAudits({ full, production, lock, installed })
  if (warning) console.warn(`::warning::${warning}`)
  else console.log('Frontend npm audits passed without an exception.')
}

if (import.meta.main) {
  try {
    run(process.argv[2])
  } catch (error) {
    console.error(`Frontend npm audit failed. ${error.message}`)
    process.exitCode = 1
  }
}
