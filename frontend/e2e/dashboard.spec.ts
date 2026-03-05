import { test, expect } from '@playwright/test'
import { loginAsAdmin } from './helpers/auth'

test.describe('Dashboard', () => {
  test('логин → панель → календарь (полный flow)', async ({ page }) => {
    await loginAsAdmin(page)
    await page.getByRole('link', { name: /календарь/i }).click()
    await expect(page).toHaveURL(/\/concierge\/calendar/)
  })

  test('неверный пароль — ошибка', async ({ page }) => {
    await page.goto('/concierge/login')
    await page.getByPlaceholder(/например: admin/i).fill('admin')
    await page.getByPlaceholder(/ваш пароль/i).fill('wrongpassword')
    await page.getByRole('button', { name: /войти/i }).click()
    await expect(page.getByText(/неверное имя пользователя или пароль/i)).toBeVisible()
  })
})
