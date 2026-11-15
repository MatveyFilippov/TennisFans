import { defineConfig } from '@playwright/test'

const port = process.env.E2E_FRONTEND_PORT ?? '4173'
const apiPort = process.env.E2E_BACKEND_PORT ?? '8005'
const origin = `http://localhost:${port}`
const apiOrigin = `http://localhost:${apiPort}`

export default defineConfig({
  testDir: './tests',
  testMatch: '*.spec.ts',
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 12_000 },
  use: { baseURL: origin, actionTimeout: 12_000, locale: 'en-US', timezoneId: 'UTC', trace: 'retain-on-failure', launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }, screenshot: 'only-on-failure' },
  webServer: [
    {
      command: 'node server.mjs', url: origin,
      env: { FRONTEND_PORT: port, FRONTEND_HOST: '127.0.0.1', PUBLIC_API_BASE_URL: apiOrigin },
    },
    {
      cwd: '../backend', command: '.venv/bin/tennisfans serve', url: `${apiOrigin}/health/ready`,
      env: {
        TENNISFANS_BACKEND_HOST: '127.0.0.1', TENNISFANS_BACKEND_PORT: apiPort,
        TENNISFANS_ALLOWED_ORIGINS: JSON.stringify([origin]),
        TENNISFANS_PUBLIC_URL: apiOrigin, TENNISFANS_RECONCILE_SECONDS: '1',
      },
    },
  ],
})
