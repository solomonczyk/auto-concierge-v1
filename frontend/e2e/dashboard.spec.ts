import { test, expect } from '@playwright/test'

/**
 * E2E: Dashboard — логин, просмотр записей.
 * Локально: admin/admin. Прод: PLAYWRIGHT_ADMIN_USER, PLAYWRIGHT_ADMIN_PASS из .env
 */
const adminUser = process.env.PLAYWRIGHT_ADMIN_USER || 'admin'
const adminPass = process.env.PLAYWRIGHT_ADMIN_PASS || 'admin'

test.describe('Dashboard', () => {
  test('логин и переход в панель', async ({ page }) => {
    await page.goto('/concierge/login')

    await expect(page.getByRole('heading', { name: /вход/i })).toBeVisible()

    await page.getByPlaceholder(/например: admin/i).fill(adminUser)
    await page.getByPlaceholder(/ваш пароль/i).fill(adminPass)
    await page.getByRole('button', { name: /войти/i }).click()

    await expect(page).toHaveURL(/\/concierge\/?$/)
    await expect(page.getByRole('heading', { name: 'Заказы' }).first()).toBeVisible({ timeout: 10000 })
  })

  test('неверный пароль — ошибка', async ({ page }) => {
    await page.goto('/concierge/login')

    await page.getByPlaceholder(/например: admin/i).fill('admin')
    await page.getByPlaceholder(/ваш пароль/i).fill('wrongpassword')
    await page.getByRole('button', { name: /войти/i }).click()

    await expect(page.getByText(/неверное имя пользователя или пароль/i)).toBeVisible()
  })

  test('после логина доступен календарь', async ({ page }) => {
    await page.goto('/concierge/login')
    await page.getByPlaceholder(/например: admin/i).fill(adminUser)
    await page.getByPlaceholder(/ваш пароль/i).fill(adminPass)
    await page.getByRole('button', { name: /войти/i }).click()

    await expect(page).toHaveURL(/\/concierge\/?$/)
    await page.getByRole('link', { name: /календарь/i }).click()
    await expect(page).toHaveURL(/\/concierge\/calendar/)
  })
})
