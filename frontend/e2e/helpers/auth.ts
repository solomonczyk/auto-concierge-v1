import { type Page, expect } from '@playwright/test'

const adminUser = process.env.PLAYWRIGHT_ADMIN_USER || 'admin'
const adminPass = process.env.PLAYWRIGHT_ADMIN_PASS || 'admin'

/**
 * Единый стабильный паттерн логина в Dashboard.
 * Ждёт отрисовку панели (dashboard-root), не URL.
 * При падении логирует статус login API для диагностики (429, CORS, etc).
 */
export async function loginAsAdmin(page: Page): Promise<void> {
  const loginStatuses: number[] = []
  page.on('response', (r) => {
    if (r.url().includes('access-token')) loginStatuses.push(r.status())
  })

  await page.goto('/concierge/login')
  await page.getByPlaceholder(/например: admin/i).fill(adminUser)
  await page.getByPlaceholder(/ваш пароль/i).fill(adminPass)
  await page.getByRole('button', { name: /войти/i }).click()

  try {
    await expect(page.getByTestId('dashboard-root')).toBeVisible({ timeout: 15000 })
  } catch (e) {
    const last = loginStatuses[loginStatuses.length - 1]
    const url = page.url()
    const diag = [
      last != null ? `Login API returned ${last}` : 'No login response captured',
      `Final URL: ${url}`,
    ].join('; ')
    throw new Error(`${(e as Error).message}. DIAG: ${diag}`)
  }
}
