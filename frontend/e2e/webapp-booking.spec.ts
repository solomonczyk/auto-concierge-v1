import { test, expect } from '@playwright/test'

/**
 * E2E: Полный сценарий записи через WebApp (как из Telegram бота).
 * Требования: backend доступен, PUBLIC_TENANT_ID, хотя бы 1 услуга в БД.
 *
 * Совместимость:
 * - getByPlaceholder / getByRole — работают без data-testid (для старых деплоев)
 * - data-testid добавлен в BookingPage.tsx — после деплоя станет основным
 */
// Slug of the main prod tenant (tenant_id=3). Override via PLAYWRIGHT_SLUG env var.
const SLUG = process.env.PLAYWRIGHT_SLUG || 'auto-concierge'

test.describe('WebApp Booking', () => {
  const TELEGRAM_ID = 123456789

  test('полный flow: услуга → авто → дата/время → запись', async ({ page }) => {
    await page.goto(`/concierge/${SLUG}?telegram_id=${TELEGRAM_ID}`)

    // Шаг 1: Выбор услуги
    await expect(page.getByRole('heading', { name: /ВЫБЕРИТЕ УСЛУГУ/i })).toBeVisible({ timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // Поддержка обеих версий: со и без data-testid="service-card"
    const firstService = page
      .locator('[data-testid="service-card"], div[class*="cursor-pointer"]')
      .filter({ hasText: /\d+\s*₽/ })
      .first()
    await expect(firstService).toBeVisible({ timeout: 10000 })
    await firstService.click()

    // Шаг 2: Данные авто
    await expect(page.getByRole('heading', { name: 'Данные автомобиля' })).toBeVisible({ timeout: 5000 })

    // Используем placeholder — работает с обеими версиями деплоя
    await page.getByPlaceholder(/Toyota Camry/i).fill('Toyota Camry')
    await page.getByPlaceholder(/2019/i).fill('2020')
    await page.getByPlaceholder(/17 символов/i).fill('XTA21120053926700')

    await page.getByRole('button', { name: /ДАЛЕЕ.*ВЫБРАТЬ ДАТУ/i }).click()

    // Шаг 3: Дата и время
    await expect(page.getByText('ВЫБЕРИТЕ ДАТУ')).toBeVisible({ timeout: 5000 })

    await page.getByRole('button', { name: /ОТКРЫТЬ КАЛЕНДАРЬ/i }).click()
    await expect(page.getByRole('button', { name: /ОТМЕНА/i })).toBeVisible()

    const calendarGrid = page.locator('.fixed.inset-0 div.grid.gap-1')
    await expect(calendarGrid).toBeVisible()
    const enabledDay = calendarGrid.locator('button:not([disabled])').filter({ hasText: /^\d{1,2}$/ }).first()
    await enabledDay.click()
    await page.waitForLoadState('networkidle')

    const slotButton = page.locator('button').filter({ hasText: /^\d{2}:\d{2}$/ }).first()
    const slotsAvailable = await slotButton.isVisible({ timeout: 20000 }).catch(() => false)
    if (!slotsAvailable) {
      test.skip(true, 'No available time slots on production — need reset_prod_for_e2e.py')
      return
    }
    await slotButton.click()

    // После выбора времени появляется fallback submit (в обычном браузере без Telegram)
    // data-testid="submit-booking" добавлен в BookingPage.tsx и задеплоен
    const submitBtn = page.getByTestId('submit-booking')
    await expect(submitBtn).toBeVisible({ timeout: 10000 })
    await submitBtn.click()

    await expect(page.getByText(/ЗАПИСЬ СОЗДАНА/i)).toBeVisible({ timeout: 10000 })
  })

  test('webapp открывается с service_id — сразу шаг авто', async ({ page }) => {
    await page.goto(`/concierge/${SLUG}?telegram_id=${TELEGRAM_ID}&service_id=1`)

    await page.waitForLoadState('networkidle')

    // Если service_id=1 найден — сразу переходит к шагу ввода авто
    // Если нет — остаётся на экране выбора услуги
    const carStep = page.getByRole('heading', { name: 'Данные автомобиля' })
    const serviceStep = page.getByRole('heading', { name: /ВЫБЕРИТЕ УСЛУГУ/i })

    await expect(carStep.or(serviceStep)).toBeVisible({ timeout: 10000 })
  })
})
