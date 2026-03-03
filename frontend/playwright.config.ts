import { defineConfig, devices } from '@playwright/test'

/**
 * E2E: WebApp, Dashboard, Bot webhook.
 *
 * Локально:
 *   npm run test:e2e
 *
 * Прод:
 *   $env:PLAYWRIGHT_BASE_URL = "https://bt-aistudio.ru"
 *   $env:PLAYWRIGHT_ADMIN_PASS = "пароль_от_дашборда"
 *   npm run test:e2e
 *
 * baseURL — корень сайта (БЕЗ /concierge).
 * Все маршруты в тестах указываются полными путями: /concierge/login, /concierge/webapp и т.д.
 */
const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173'
const isLocal = baseURL.includes('localhost')

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: isLocal
    ? {
        command: 'npm run dev',
        url: 'http://localhost:5173/concierge',
        reuseExistingServer: true,
        timeout: 60_000,
      }
    : undefined,
})
