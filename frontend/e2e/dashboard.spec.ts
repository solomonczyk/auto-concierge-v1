import { test, expect } from '@playwright/test'
import { loginAsAdmin } from './helpers/auth'

/**
 * Dashboard tests — используют API-auth (стабильно).
 * UI логина тестируется в auth-ui.spec.ts.
 */
test.describe('Dashboard', () => {
  test('панель → календарь (полный flow)', async ({ page }) => {
    await loginAsAdmin(page)
    await page.getByRole('link', { name: /календарь/i }).click()
    await expect(page).toHaveURL(/\/concierge\/calendar/)
  })
})
