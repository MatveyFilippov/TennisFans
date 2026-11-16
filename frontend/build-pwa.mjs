import { createHash } from 'node:crypto'
import { readdir, readFile, writeFile } from 'node:fs/promises'

const assets = ['/index.html', '/manifest.webmanifest', '/icons/icon-192.png', '/icons/icon-512.png', '/icons/icon-maskable.png']
assets.push(...(await readdir('dist/assets')).map(name => '/assets/' + name).sort())
const source = await readFile('service-worker.js', 'utf8')
const hash = createHash('sha256').update(source)
for (const path of assets) hash.update(await readFile('dist' + path))
await writeFile('dist/sw.js', source
  .replace("'__TENNISFANS_REVISION__'", JSON.stringify(hash.digest('hex').slice(0, 16)))
  .replace("['__TENNISFANS_ASSETS__']", JSON.stringify(assets)))
