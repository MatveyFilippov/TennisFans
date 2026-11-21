import { createHash } from 'node:crypto'
import { readdir, readFile, writeFile } from 'node:fs/promises'

const assets = ['/index.html', '/manifest.webmanifest']
// Preserve the original artwork as a reference without downloading it on every PWA install.
assets.push(...(await readdir('dist/brand')).filter(name => name !== 'court-original-transparent.png')
  .map(name => '/brand/' + name).sort())
assets.push(...(await readdir('dist/assets')).map(name => '/assets/' + name).sort())
const source = await readFile('service-worker.js', 'utf8')
const hash = createHash('sha256').update(source)
for (const path of assets) hash.update(path).update(await readFile('dist' + path))
await writeFile('dist/sw.js', source
  .replace("'__TENNISFANS_REVISION__'", JSON.stringify(hash.digest('hex').slice(0, 16)))
  .replace("['__TENNISFANS_ASSETS__']", JSON.stringify(assets)))
