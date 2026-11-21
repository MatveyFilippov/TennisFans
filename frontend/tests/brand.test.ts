import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { cpSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { expect, it } from 'vitest'

const brand = resolve('public/brand')

it('preserves the supplied transparent original byte for byte', () => {
  expect(createHash('sha256').update(readFileSync(join(brand, 'court-original-transparent.png'))).digest('hex'))
    .toBe('f34c8f223479bb556afb2b7a352a73792e14902df7725de69c9fa4b9ef75919a')
})

it('uses correctly sized court icons and preserves the PWA identity', () => {
  const manifest = JSON.parse(readFileSync('public/manifest.webmanifest', 'utf8'))
  expect([manifest.id, manifest.start_url, manifest.scope]).toEqual(['/', '/', '/'])
  expect(manifest.icons).toEqual([
    { src: '/brand/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
    { src: '/brand/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
    { src: '/brand/icon-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
  ])
  for (const [name, size] of Object.entries({
    'icon-192.png': 192, 'icon-512.png': 512, 'icon-maskable.png': 512,
    'apple-touch-icon.png': 180, 'favicon-16.png': 16, 'favicon-32.png': 32,
  })) {
    const png = readFileSync(join(brand, name))
    expect(png.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a')
    expect([png.readUInt32BE(16), png.readUInt32BE(20)]).toEqual([size, size])
  }
})

it('precaches all runtime brand assets and revises the shell when their bytes change', () => {
  const directory = mkdtempSync(join(tmpdir(), 'tennisfans-brand-pwa-'))
  try {
    cpSync('public', join(directory, 'dist'), { recursive: true })
    mkdirSync(join(directory, 'dist/assets'))
    writeFileSync(join(directory, 'dist/assets/bundle.js'), 'export {}')
    cpSync('index.html', join(directory, 'dist/index.html'))
    cpSync('service-worker.js', join(directory, 'service-worker.js'))
    const build = () => {
      execFileSync(process.execPath, [resolve('build-pwa.mjs')], { cwd: directory })
      return readFileSync(join(directory, 'dist/sw.js'), 'utf8')
    }
    const first = build()
    const assets: string[] = JSON.parse(first.match(/^const assets = (.+)$/m)![1])
    expect(assets.filter(path => path.startsWith('/brand/'))).toEqual(readdirSync(brand)
      .filter(name => name !== 'court-original-transparent.png').map(name => '/brand/' + name).sort())
    expect(assets.some(path => path.startsWith('/icons/'))).toBe(false)
    for (const path of assets) expect(readFileSync(join(directory, 'dist', path)).length).toBeGreaterThan(0)
    const mark = join(directory, 'dist/brand/court-mark.svg')
    writeFileSync(mark, readFileSync(mark, 'utf8') + '\n')
    expect(build().match(/^const revision = (.+)$/m)![1]).not.toBe(first.match(/^const revision = (.+)$/m)![1])
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
})
