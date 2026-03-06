import { test, expect } from '@playwright/test'
import { loginAsAdminViaUI } from './helpers/auth'

/**
 * UI Login smoke test — проверка, что форма логина реально работает.
 * Отдельно от остальных тестов, которые используют API-auth.
 */
test.describe('Auth UI (smoke)', () => {
  test('успешный логин через форму → редирект на dashboard', async ({ page }) => {
    await loginAsAdminViaUI(page)
  })

  test('неверный пароль — показ ошибки', async ({ page }) => {
    await page.goto('/concierge/login')
    await page.getByPlaceholder(/например: admin/i).fill('admin')
    await page.getByPlaceholder(/ваш пароль/i).fill('wrongpassword')
    await page.getByRole('button', { name: /войти/i }).click()
    await expect(page.getByText(/неверное имя пользователя или пароль/i)).toBeVisible()
  })
})
