import assert from 'node:assert/strict'
import { test } from 'node:test'
import { evaluateAudits } from './frontend-audit.mjs'

const active = Date.parse('2026-11-18T12:00:00Z')
const expired = Date.parse('2026-12-18T00:00:00Z')
const locationOf = name => `node_modules/${name}`

function advisory(name, severity, id = 'GHSA-fc5q-39xc-vjpf') {
  return { name, dependency: name, severity, url: `https://github.com/advisories/${id}` }
}

function entry(name, via, severity = 'high') {
  return { name, severity, via, nodes: [locationOf(name)] }
}

function report(...entries) {
  const counts = { info: 0, low: 0, moderate: 0, high: 0, critical: 0, total: entries.length }
  for (const { severity } of entries) counts[severity]++
  const vulnerabilities = Object.fromEntries(entries.map(item => [item.name, item]))
  return {
    status: counts.moderate || counts.high || counts.critical ? 1 : 0,
    stdout: JSON.stringify({
      auditReportVersion: 2, vulnerabilities, metadata: { vulnerabilities: counts },
    }),
  }
}

function fixture() {
  const known = entry('picomatch', [advisory('picomatch', 'high')])
  const vitest = entry('vitest', ['picomatch', '@vitest/coverage-v8'])
  const coverage = entry('@vitest/coverage-v8', ['vitest'])
  const installed = [
    { location: '', name: 'tennisfans-frontend', version: '1.0.0', dev: false },
    { location: locationOf('picomatch'), name: 'picomatch', version: '4.0.7', dev: true },
    { location: locationOf('vitest'), name: 'vitest', version: '4.1.12', dev: true },
    { location: locationOf('@vitest/coverage-v8'), name: '@vitest/coverage-v8', version: '4.1.12', dev: true },
  ]
  const packages = Object.fromEntries(installed.map(({ location, ...node }) => [location, node]))
  return {
    known, vitest, coverage,
    input: { full: report(known, vitest, coverage), production: report(), installed, lock: { lockfileVersion: 3, packages } },
  }
}

test('a clean audit passes without an exception', () => {
  const { input } = fixture()
  input.full = report()
  assert.equal(evaluateAudits(input, active), null)
})

test('the named dev-only advisory and its transitive cycle produce an expiry warning', () => {
  const { input } = fixture()
  const warning = evaluateAudits(input, expired - 1)
  assert.match(warning, /SECURITY EXCEPTION ACTIVE.*GHSA-fc5q-39xc-vjpf.*picomatch@4\.0\.7/)
  assert.match(warning, /devDependencies only.*2026-12-18T00:00:00Z/)
})

for (const severity of ['moderate', 'high', 'critical']) {
  test(`an unrelated ${severity} advisory still blocks`, () => {
    const { input, known } = fixture()
    const other = entry('unrelated', [advisory('unrelated', severity, 'GHSA-0000-0000-0000')], severity)
    input.full = report(known, other)
    assert.throws(() => evaluateAudits(input, active), /outside the exception/)
  })
}

test('an unrelated low advisory remains below the threshold', () => {
  const { input, known } = fixture()
  input.full = report(known, entry('unrelated', [advisory('unrelated', 'low', 'GHSA-0000-0000-0000')], 'low'))
  assert.match(evaluateAudits(input, active), /SECURITY EXCEPTION ACTIVE/)
})

test('a different advisory on picomatch itself blocks even when the approved one is present', () => {
  const { input, known, vitest, coverage } = fixture()
  known.via.push(advisory('picomatch', 'moderate', 'GHSA-0000-0000-0000'))
  input.full = report(known, vitest, coverage)
  assert.throws(() => evaluateAudits(input, active), /outside the exception/)
})

test('the approved advisory cannot be applied to another picomatch version', () => {
  const { input } = fixture()
  input.installed[1].version = '4.0.6'
  input.lock.packages[locationOf('picomatch')].version = '4.0.6'
  assert.throws(() => evaluateAudits(input, active), /approved version/)
})

test('a blocking production report is an independent failure', () => {
  const { input, known } = fixture()
  input.production = report(known)
  assert.throws(() => evaluateAudits(input, active), /Production npm audit found/)
})

test('a production picomatch entry blocks in either source, even with a clean audit', () => {
  const inventoryOnly = fixture().input
  inventoryOnly.full = report()
  inventoryOnly.installed.push({
    location: locationOf('glob-alias'), name: 'picomatch', version: '4.0.7', dev: false,
  })
  assert.throws(() => evaluateAudits(inventoryOnly, active), /outside the frontend dev/)

  const lockOnly = fixture().input
  lockOnly.full = report()
  lockOnly.lock.packages['node_modules/parent/node_modules/picomatch'] = { version: '4.0.7' }
  assert.throws(() => evaluateAudits(lockOnly, active), /outside the frontend dev/)
})

test('an affected parent must also be dev-only in both sources', () => {
  const { input } = fixture()
  input.lock.packages[locationOf('vitest')].dev = false
  assert.throws(() => evaluateAudits(input, active), /Cannot verify dev-only scope/)
})

test('the exception expires at the exact UTC deadline', () => {
  const { input } = fixture()
  assert.throws(() => evaluateAudits(input, expired), /expired/)
})

test('a patched dev dependency and clean report pass after expiry', () => {
  const { input } = fixture()
  input.full = report()
  input.lock.packages[locationOf('picomatch')].version = '4.0.8'
  input.installed[1].version = '4.0.8'
  assert.equal(evaluateAudits(input, expired + 1), null)
})

test('invalid JSON blocks', () => {
  const { input } = fixture()
  input.full = { status: 1, stdout: '{incomplete' }
  assert.throws(() => evaluateAudits(input, active), /valid JSON/)
})

test('registry errors, spawn errors, signals and unknown exit codes block', () => {
  const { input } = fixture()
  input.full = { status: 1, stdout: '{"error":{"code":"E503"}}' }
  assert.throws(() => evaluateAudits(input, active), /returned an error/)
  for (const failure of [{ error: new Error('ENOENT') }, { signal: 'SIGTERM' }, { status: 2 }]) {
    input.full = { ...report(), ...failure }
    assert.throws(() => evaluateAudits(input, active), /did not complete/)
  }
})

test('an unsupported report or inconsistent exit status blocks', () => {
  const { input } = fixture()
  input.production = { status: 0, stdout: '{"auditReportVersion":1,"vulnerabilities":{}}' }
  assert.throws(() => evaluateAudits(input, active), /unsupported report/)
  input.production = { ...report(), status: 1 }
  assert.throws(() => evaluateAudits(input, active), /disagree with the report/)
})

test('broken references and cycles with no advisory block, even alongside the approved advisory', () => {
  const { input, known, vitest, coverage } = fixture()
  vitest.via.push('missing')
  input.full = report(known, vitest, coverage)
  assert.throws(() => evaluateAudits(input, active), /unresolved/)
  input.full = report(known, entry('vitest', ['@vitest/coverage-v8']), coverage)
  assert.throws(() => evaluateAudits(input, active), /Unresolved npm advisory chain/)
})
