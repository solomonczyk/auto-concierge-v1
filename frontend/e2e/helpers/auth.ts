import { type Page, expect } from '@playwright/test'

const adminUser = process.env.PLAYWRIGHT_ADMIN_USER || 'admin'
const adminPass = process.env.PLAYWRIGHT_ADMIN_PASS || 'admin'
const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173'

/**
 * Login via API — cookie-based auth only.
 * Backend sets Set-Cookie; Playwright request context stores it; page.goto sends cookies.
 * No localStorage, no token in URL/body.
 */
export async function loginAsAdmin(page: Page): Promise<void> {
  const apiUrl = `${baseURL.replace(/\/$/, '')}/concierge/api/v1/login/access-token`
  const res = await page.request.post(apiUrl, {
    form: { username: adminUser, password: adminPass },
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  if (res.status() !== 200) {
    throw new Error(`Login API returned ${res.status()}`)
  }
  // Backend sets Set-Cookie; request context stores it for same-origin
  await page.goto('/concierge/')
  await expect(page.getByTestId('dashboard-root')).toBeVisible({ timeout: 15000 })
}

/**
 * UI-based login — only for auth-ui smoke test.
 */
export async function loginAsAdminViaUI(page: Page): Promise<void> {
  await page.goto('/concierge/login')
  await page.getByPlaceholder(/например: admin/i).fill(adminUser)
  await page.getByPlaceholder(/ваш пароль/i).fill(adminPass)
  await page.getByRole('button', { name: /войти/i }).click()
  await page.waitForURL(/concierge/)
  await expect(page.getByTestId('dashboard-root')).toBeVisible({ timeout: 15000 })
}
