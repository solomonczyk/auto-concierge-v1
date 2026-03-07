import { type Page, expect } from '@playwright/test'

const adminUser = process.env.PLAYWRIGHT_ADMIN_USER || 'admin'
const adminPass = process.env.PLAYWRIGHT_ADMIN_PASS || 'admin'
const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173'

/**
 * Login via API — supports both cookie-based and legacy JSON-token auth.
 *
 * Cookie-based (new): backend sets Set-Cookie, browser picks it up.
 * Legacy JSON (old):  backend returns { access_token }, we inject it
 *                     as a cookie manually so the SPA can read it.
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

  const body = await res.json()

  if (body.access_token) {
    const domain = new URL(baseURL).hostname
    await page.context().addCookies([
      {
        name: 'access_token',
        value: body.access_token,
        domain,
        path: '/',
        httpOnly: true,
        secure: baseURL.startsWith('https'),
        sameSite: 'Lax',
      },
    ])
    // Legacy frontend reads token from localStorage
    const token = body.access_token
    await page.addInitScript((t) => { localStorage.setItem('token', t) }, token)
  }

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
