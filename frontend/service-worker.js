const revision = '__TENNISFANS_REVISION__'
const assets = ['__TENNISFANS_ASSETS__']
const shell = `tennisfans-shell-${revision}`
const publicCache = 'tennisfans-public-v1'
const limit = 120

self.addEventListener('install', event => {
  event.waitUntil(caches.open(shell).then(cache => cache.addAll([...assets, '/config.json'])))
})
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith('tennisfans-shell-') && key !== shell) await caches.delete(key)
    }
    await self.clients.claim()
  })())
})
self.addEventListener('message', event => {
  if (event.data === 'UPDATE') void self.skipWaiting()
})

async function networkFirst(request, cacheName, fallback, timeout, publicRead = false) {
  const cache = await caches.open(cacheName)
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeout)
    const response = await fetch(request, { signal: controller.signal }).finally(() => clearTimeout(timer))
    if (response.status === 404 && publicRead) await cache.delete(request)
    if (response.ok && !publicRead && request.url.endsWith('/config.json')) {
      await cache.put(request, response.clone())
    }
    if (response.ok && publicRead && response.headers.get('X-TennisFans-Public') === '1') {
      await cache.delete(request)
      await cache.put(request, response.clone())
      const keys = await cache.keys()
      await Promise.all(keys.slice(0, Math.max(0, keys.length - limit)).map(key => cache.delete(key)))
    }
    if (response.status < 500) return response
    throw new Error('Upstream unavailable')
  } catch {
    const cached = await cache.match(fallback ?? request)
    if (cached) {
      if (publicRead) {
        for (const client of await self.clients.matchAll({ type: 'window' })) {
          client.postMessage('STALE_PUBLIC_DATA')
        }
      }
      return cached
    }
    return new Response(JSON.stringify({ code: 'offline', detail: '' }), {
      status: 503, headers: { 'Content-Type': 'application/json' },
    })
  }
}

self.addEventListener('fetch', event => {
  const request = event.request
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (url.origin === self.location.origin) {
    if (request.mode === 'navigate') {
      event.respondWith(networkFirst(request, shell, '/index.html', 2200))
      return
    }
    if (assets.includes(url.pathname)) {
      event.respondWith(caches.open(shell).then(async cache => await cache.match(request) ?? fetch(request)))
      return
    }
    if (url.pathname === '/config.json') {
      event.respondWith(networkFirst(request, shell, null, 1500))
      return
    }
  }
  if (url.pathname.startsWith('/api/v1/public/')) {
    event.respondWith((async () => {
      const cache = await caches.open(shell)
      const response = await cache.match('/config.json')
      const config = await response?.json().catch(() => null)
      const apiOrigin = new URL(config?.apiBaseUrl || self.location.origin).origin
      return url.origin === apiOrigin ? networkFirst(request, publicCache, null, 3200, true) : fetch(request)
    })())
  }
})
