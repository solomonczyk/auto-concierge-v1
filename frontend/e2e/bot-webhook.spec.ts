import { test, expect } from '@playwright/test'

/**
 * E2E: Webhook бота — симуляция входящего Update от Telegram.
 * Локально: webhook на http://localhost:8000/api/v1/webhook
 * Прод:     webhook на https://bt-aistudio.ru/concierge/api/v1/webhook
 *           (nginx: /concierge/api/ → :8002/api/)
 */
const BASE = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:8000'
// На проде frontend и API за одним доменом, webhook путь отличается
const WEBHOOK_URL = BASE.includes('localhost')
  ? `${BASE}/api/v1/webhook`
  : `${BASE}/concierge/api/v1/webhook`

test.describe('Bot Webhook', () => {
  const minimalUpdate = {
    update_id: Math.floor(Math.random() * 1e9),
    message: {
      message_id: 1,
      date: Math.floor(Date.now() / 1000),
      chat: {
        id: 123456,
        type: 'private',
        username: 'e2e_test',
      },
      from: {
        id: 123456,
        is_bot: false,
        first_name: 'E2E',
        username: 'e2e_test',
      },
      text: '/start',
    },
  }

  test('принимает Update и возвращает ok', async ({ request }) => {
    const res = await request.post(WEBHOOK_URL, {
      data: minimalUpdate,
      headers: { 'Content-Type': 'application/json' },
    })

    if (res.status() === 403) {
      test.skip(true, 'TELEGRAM_WEBHOOK_SECRET задан — нужен заголовок x-telegram-bot-api-secret-token')
    }

    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body.status).toBe('ok')
  })

  test('повторный Update — idempotent', async ({ request }) => {
    const update = { ...minimalUpdate, update_id: 999888777 }
    const res1 = await request.post(WEBHOOK_URL, {
      data: update,
      headers: { 'Content-Type': 'application/json' },
    })

    if (res1.status() === 403) test.skip(true, 'Webhook secret required')

    expect(res1.status()).toBe(200)

    const res2 = await request.post(WEBHOOK_URL, {
      data: update,
      headers: { 'Content-Type': 'application/json' },
    })
    expect(res2.status()).toBe(200)
    const body = await res2.json()
    expect(body.msg).toBe('already_processed')
  })
})
