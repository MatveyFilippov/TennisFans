import { createReadStream } from 'node:fs'
import { stat } from 'node:fs/promises'
import { createServer } from 'node:http'
import { resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('./dist', import.meta.url))
const api = process.env.PUBLIC_API_BASE_URL ?? ''
const apiOrigin = api ? new URL(api).origin : ''
if (api && (!['http:', 'https:'].includes(new URL(api).protocol) || api !== apiOrigin)) {
  throw new Error('PUBLIC_API_BASE_URL must be an HTTP(S) origin without a path')
}
const host = process.env.FRONTEND_HOST ?? '127.0.0.1'
const port = Number(process.env.FRONTEND_PORT ?? 5173)
const types = {
  html: 'text/html; charset=utf-8', css: 'text/css; charset=utf-8',
  js: 'application/javascript; charset=utf-8', json: 'application/json',
  webmanifest: 'application/manifest+json', png: 'image/png', woff2: 'font/woff2',
}

createServer(async (req, res) => {
  res.setHeader('X-Content-Type-Options', 'nosniff')
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin')
  res.setHeader('X-Frame-Options', 'DENY')
  res.setHeader('Content-Security-Policy', [
    "default-src 'self'", "base-uri 'none'", "frame-ancestors 'none'", "object-src 'none'",
    "style-src 'self'", "script-src 'self'", "worker-src 'self'",
    `connect-src 'self' ${apiOrigin}`, `img-src 'self' blob: ${apiOrigin}`,
  ].join('; '))
  res.setHeader('Cache-Control', 'no-cache')
  if (!['GET', 'HEAD'].includes(req.method ?? '')) {
    res.writeHead(405, { Allow: 'GET, HEAD' }).end()
    return
  }
  try {
    const path = decodeURIComponent(new URL(req.url, 'http://localhost').pathname)
    if (path === '/config.json') {
      res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' })
      res.end(req.method === 'HEAD' ? undefined : JSON.stringify({ apiBaseUrl: api }))
      return
    }
    if (path === '/health/live') {
      res.writeHead(200, { 'Content-Type': 'application/json' }).end(JSON.stringify({
        status: 'ok', version: '1.0.0', commit: process.env.TENNISFANS_BUILD_SHA ?? 'local',
      }))
      return
    }
    const requested = resolve(root, '.' + path)
    if (requested !== root && !requested.startsWith(root + sep)) {
      res.writeHead(404).end()
      return
    }
    const name = path.split('/').at(-1)
    const extension = name?.includes('.') ? name.split('.').at(-1) : 'html'
    const file = extension === 'html' && !name?.endsWith('.html') ? resolve(root, 'index.html') : requested
    if (!types[extension]) {
      res.writeHead(404).end()
      return
    }
    const fileStat = await stat(file)
    if (!fileStat.isFile()) {
      res.writeHead(404).end()
      return
    }
    if (path.startsWith('/assets/')) {
      res.setHeader('Cache-Control', 'public, max-age=31536000, immutable')
    }
    res.writeHead(200, { 'Content-Type': types[extension], 'Content-Length': fileStat.size })
    if (req.method === 'HEAD') {
      res.end()
    } else {
      const stream = createReadStream(file)
      stream.on('error', () => res.destroy())
      stream.pipe(res)
    }
  } catch (error) {
    res.writeHead(error instanceof URIError ? 400 : 404).end()
  }
}).listen(port, host, () => console.log(`TennisFans frontend listening on http://${host}:${port}`))
