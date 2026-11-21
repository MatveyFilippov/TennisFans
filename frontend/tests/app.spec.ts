import { randomBytes } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const api = `http://localhost:${process.env.E2E_BACKEND_PORT ?? '8005'}/api/v1`
const origin = `http://localhost:${process.env.E2E_FRONTEND_PORT ?? '4173'}`
const password = 'browser test password'
const adminPassword = process.env.TEST_ADMIN_PASSWORD ?? ''
const prefix = randomBytes(4).toString('hex')

async function signIn(page: Page, username: string, pass = password) {
  await page.goto('/login')
  await page.getByLabel('Username').fill(username)
  await page.getByLabel('Password', { exact: true }).fill(pass)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).toHaveURL(/\/account$/)
}

async function register(request: APIRequestContext, username: string, displayName: string) {
  const response = await request.post(api + '/auth/register', {
    headers: { Origin: origin }, data: { username, password, display_name: displayName },
  })
  expect(response.status()).toBe(201)
  return (await response.json()).user.id as string
}

async function pick(page: Page, label: string, username: string) {
  const input = page.getByRole('searchbox', { name: label, exact: true })
  await input.fill(username)
  await input.locator('..').getByRole('button', { name: new RegExp('@' + username) }).click()
}

async function singleSet(page: Page, a: string, b: string) {
  await page.getByLabel('Games or deciding points A').fill(a)
  await page.getByLabel('Games or deciding points B').fill(b)
}

async function courtBrand(page: Page, header: string, footer: string) {
  for (const [selector, source] of [['.site-header .brand', header], ['.site-footer .brand', footer]]) {
    const link = page.locator(selector)
    await expect(link).toHaveAccessibleName('TennisFans')
    await expect(link).toHaveAttribute('href', '/')
    await expect(link).toHaveText('')
    const image = link.locator('img:visible')
    await expect(image).toHaveCount(1)
    await expect(image).toHaveAttribute('src', `/brand/court-mark${source}.svg`)
    await expect(image).toHaveAttribute('alt', '')
    await expect.poll(() => image.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true)
  }
}

for (const width of [320, 375, 768, 1280]) {
  test(`fits a ${width}px viewport and localizes navigation`, async ({ page }, testInfo) => {
    const errors: string[] = []
    page.on('pageerror', error => errors.push(String(error)))
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
    await page.setViewportSize({ width, height: 840 })
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'TennisFans', exact: true, level: 1 })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Your tennis, on the record.' })).toBeVisible()
    await expect(page.locator('.hero-photo')).toHaveJSProperty('complete', true)
    expect(await page.locator('.hero-photo').evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0)
    await expect(page.locator('.skeleton')).toHaveCount(0)
    await courtBrand(page, '-light', '')
    await page.screenshot({ path: testInfo.outputPath('home.png'), fullPage: true })
    for (const path of ['/ratings', '/matches', '/tournaments', '/register']) {
      await page.goto(path)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      await courtBrand(page, '', '')
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    }
    await page.getByRole('combobox', { name: 'Language' }).selectOption('ru')
    await expect(page.getByRole('heading', { name: 'Регистрация' })).toBeVisible()
    await page.reload()
    await expect(page.locator('html')).toHaveAttribute('lang', 'ru')
    await page.getByRole('combobox', { name: 'Тема' }).selectOption('dark')
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
    await courtBrand(page, '-light', '-light')
    await page.getByRole('combobox', { name: 'Тема' }).selectOption('system')
    await page.emulateMedia({ colorScheme: 'dark' })
    await courtBrand(page, '-light', '-light')
    await page.emulateMedia({ colorScheme: 'light' })
    await courtBrand(page, '', '')
    await page.emulateMedia({ colorScheme: 'dark' })
    await page.getByRole('combobox', { name: 'Тема' }).selectOption('light')
    await courtBrand(page, '', '')
    expect(errors).toEqual([])
  })
}

test('installs the app shell and shows previously loaded public content offline', async ({ page, context, request }) => {
  const manifest = await (await request.get('/manifest.webmanifest')).json()
  expect(manifest.display).toBe('standalone')
  expect(manifest.icons.map((icon: { sizes: string }) => icon.sizes)).toContain('512x512')
  await page.goto('/ratings')
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true)
  const brandPaths = ['/brand/court-mark.svg', '/brand/court-mark-light.svg', '/brand/favicon.svg',
    '/brand/favicon-16.png', '/brand/favicon-32.png', '/brand/apple-touch-icon.png',
    '/brand/icon-192.png', '/brand/icon-512.png', '/brand/icon-maskable.png']
  for (const path of brandPaths) {
    const response = await request.get(path)
    expect(response.status()).toBe(200)
    expect(response.headers()['content-type']).toBe(path.endsWith('.svg') ? 'image/svg+xml' : 'image/png')
  }
  const artwork = await page.evaluate(async () => Promise.all(
    ['favicon-16.png', 'favicon-32.png', 'icon-192.png', 'icon-512.png'].map(async name => {
      const image = await createImageBitmap(await (await fetch('/brand/' + name)).blob())
      const canvas = new OffscreenCanvas(image.width, image.height)
      const context = canvas.getContext('2d')!
      context.drawImage(image, 0, 0)
      const { data, width, height } = context.getImageData(0, 0, image.width, image.height)
      let left = width, right = -1, top = height, bottom = -1, maxAlpha = 0
      for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
        const alpha = data[(y * width + x) * 4 + 3]
        maxAlpha = Math.max(maxAlpha, alpha)
        if (alpha) {
          left = Math.min(left, x); right = Math.max(right, x)
          top = Math.min(top, y); bottom = Math.max(bottom, y)
        }
      }
      return { name, width, height, inkWidth: right - left + 1, inkHeight: bottom - top + 1, maxAlpha,
        corners: [3, (width - 1) * 4 + 3, (height - 1) * width * 4 + 3, data.length - 1].map(index => data[index]) }
    }),
  ))
  for (const image of artwork) {
    expect(image.width).toBe(image.height)
    expect(image.inkWidth / image.width).toBeGreaterThanOrEqual(.85)
    expect(image.maxAlpha).toBe(255)
    expect(image.corners).toEqual([0, 0, 0, 0])
    if (image.name.startsWith('favicon')) expect(image.inkHeight / image.height).toBeGreaterThanOrEqual(.6)
    else expect(image.inkWidth / image.inkHeight).toBeCloseTo(784 / 480, 1)
  }
  await page.reload()
  await expect.poll(() => page.evaluate(async () => {
    const cache = await caches.open('tennisfans-public-v1')
    return (await cache.keys()).some(entry => new URL(entry.url).pathname === '/api/v1/public/ratings')
  })).toBe(true)
  await context.setOffline(true)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Ratings' })).toBeVisible()
  await expect(page.getByRole('status').filter({ hasText: 'Offline' })).toBeVisible()
  await courtBrand(page, '', '')
  expect(await page.evaluate(async paths => Promise.all(paths.map(async path => (await fetch(path)).ok)), brandPaths))
    .toEqual(brandPaths.map(() => true))
  await expect(page.getByText('The application configuration could not be loaded.')).toHaveCount(0)
  const publicPaths = await page.evaluate(async () => {
    const cache = await caches.open('tennisfans-public-v1')
    return (await cache.keys()).map(request => new URL(request.url).pathname)
  })
  expect(publicPaths.every(path => path.startsWith('/api/v1/public/'))).toBe(true)
  await context.setOffline(false)
})

for (const width of [375, 1280]) {
  test(`records, rates, disputes, and completes matches at ${width}px`, async ({ browser, page, request }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    const code = prefix + width
    const alice = 'alice-' + code, bob = 'bob-' + code, dana = 'dana-' + code, organizer = 'org-' + code
    const aliceName = 'Alice ' + code, bobName = 'Bob ' + code, danaName = 'Dana ' + code, organizerName = 'Organizer ' + code
    const players = await Promise.all([
      register(request, bob, bobName), register(request, dana, danaName), register(request, organizer, organizerName),
    ])
    await page.goto('/register')
    await page.getByLabel('Username').fill(alice)
    await page.getByLabel('Display name').fill(aliceName)
    await page.getByLabel('Password', { exact: true }).fill(password)
    await page.getByRole('button', { name: 'Create account', exact: true }).click()
    await expect(page).toHaveURL(/\/account$/)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)

    await page.goto('/friendlies/new')
    await pick(page, 'Choose a player', bob)
    await page.getByRole('combobox', { name: 'Format', exact: true }).selectOption('SINGLE_SET')
    await singleSet(page, '6', '4')
    await page.getByRole('button', { name: 'Submit result', exact: true }).click()
    await expect(page).toHaveURL(/\/matches\//)
    const friendly = page.url()
    await expect(page.getByText('6:4')).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await expect(page.getByText(/Alice .*1516/)).toBeVisible()
    await page.locator('input[type="file"]').setInputFiles({
      name: 'tennis.png', mimeType: 'image/png',
      buffer: readFileSync('public/brand/icon-192.png'),
    })
    await page.getByRole('button', { name: 'Upload photos' }).click()
    await expect(page.getByRole('link', { name: 'Open photo' })).toBeVisible()
    await page.goto('/friendlies/new')
    await page.getByLabel('Discipline').selectOption('DOUBLES')
    await pick(page, 'As partners', dana)
    await pick(page, 'Choose a player', bob)
    await pick(page, 'Second opponent', organizer)
    await page.getByRole('combobox', { name: 'Format', exact: true }).selectOption('SHORT_MATCH')
    await singleSet(page, '3', '2')
    await page.getByRole('button', { name: 'Submit result', exact: true }).click()
    await expect(page.getByText('3:2')).toBeVisible()
    await page.goto('/ratings')
    await expect(page.getByRole('link', { name: aliceName })).toBeVisible()

    const other = await browser.newContext({ locale: 'en-US', timezoneId: 'UTC', viewport: { width, height: 900 } })
    const p = await other.newPage()
    await signIn(p, bob)
    await p.goto(friendly)
    await p.getByRole('button', { name: 'Dispute result' }).click()
    const dispute = p.getByRole('heading', { name: 'Dispute result' }).locator('../..')
    await dispute.getByLabel('Reason').fill('Please verify the sets.')
    await dispute.getByRole('button', { name: 'Dispute result' }).click()
    await expect(p.getByText('Disputed', { exact: true })).toBeVisible()
    await expect(p.getByText(/Alice .*1516/)).toHaveCount(0)

    const adminContext = await browser.newContext({ locale: 'en-US', timezoneId: 'UTC', viewport: { width, height: 900 } })
    const admin = await adminContext.newPage()
    await signIn(admin, 'browser-admin', adminPassword)
    await admin.goto(friendly)
    await admin.getByRole('button', { name: 'Resolve dispute' }).click()
    const resolution = admin.getByRole('heading', { name: 'Resolve dispute' }).locator('../..')
    await resolution.getByLabel('Reason').fill('Score verified on the scoresheet.')
    await resolution.getByRole('button', { name: 'Resolve dispute' }).click()
    await expect(admin.getByText('Completed', { exact: true })).toBeVisible()

    const tourName = 'Morning Cup ' + code
    await admin.goto('/tournaments/new')
    await admin.getByLabel('Title').fill(tourName)
    await admin.getByLabel('Player slots').fill('2')
    await admin.getByLabel('Date and time').fill(new Date(Date.now() + 28_000).toISOString().slice(0, 23))
    await admin.getByRole('group', { name: 'Roster', exact: true }).getByRole('searchbox').fill(alice)
    await admin.getByRole('group', { name: 'Roster', exact: true }).getByRole('button', { name: new RegExp(alice) }).click()
    await admin.getByRole('group', { name: 'Organizers', exact: true }).getByRole('searchbox').fill(organizer)
    await admin.getByRole('group', { name: 'Organizers', exact: true }).getByRole('button', { name: new RegExp(organizer) }).click()
    await admin.getByRole('group', { name: 'Scoring', exact: true }).getByRole('combobox', { name: 'Format', exact: true }).selectOption('SINGLE_SET')
    await admin.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(admin.getByRole('heading', { name: tourName })).toBeVisible()
    const tour = admin.url()
    await p.goto(tour)
    await p.getByRole('button', { name: 'Apply', exact: true }).click()
    await expect(p.getByText('Pending', { exact: true })).toBeVisible()
    const managerContext = await browser.newContext({ locale: 'en-US', timezoneId: 'UTC', viewport: { width, height: 900 } })
    const manager = await managerContext.newPage()
    await signIn(manager, organizer)
    await manager.goto(tour)
    await manager.getByRole('button', { name: 'Accept', exact: true }).click()
    await expect(manager.getByText('Accepted players: 2/2')).toBeVisible()
    await expect.poll(async () => {
      const checked = await request.get(api + '/public/tournaments/' + tour.split('/').pop())
      return (await checked.json()).status
    }, { timeout: 40_000 }).toBe('ACTIVE')
    await page.goto(tour)
    await page.getByRole('link', { name: 'Details', exact: true }).click()
    await page.getByRole('button', { name: 'Submit result' }).click()
    const result = page.getByRole('heading', { name: 'Submit result' }).locator('../..')
    await singleSet(page, '6', '1')
    await result.getByRole('button', { name: 'Submit result' }).click()
    await expect(page.getByText('6:1')).toBeVisible()
    await admin.goto(tour)
    await expect(admin.getByText('Completed', { exact: true }).first()).toBeVisible()
    await expect(admin.getByRole('heading', { name: 'Standings' })).toBeVisible()
    expect(await admin.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await admin.screenshot({ path: testInfo.outputPath('completed-tournament.png'), fullPage: true })
    await admin.getByRole('button', { name: 'Permanently delete tournament' }).click()
    await admin.getByRole('button', { name: 'Confirm', exact: true }).click()
    await expect(admin).toHaveURL(/\/tournaments$/)
    expect((await request.get(api + '/public/tournaments/' + tour.split('/').pop())).status()).toBe(404)
    const bobStats = await (await request.get(api + '/public/users/' + players[0])).json()
    expect(bobStats.overall.matches).toBe(2)
    await Promise.all([other.close(), adminContext.close(), managerContext.close()])
  })
}
