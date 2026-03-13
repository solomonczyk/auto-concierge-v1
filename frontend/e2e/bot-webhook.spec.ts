import { test, expect } from '@playwright/test'

/**
 * E2E: Webhook бота — симуляция входящего Update от Telegram.
 * Использует PLAYWRIGHT_API_URL (backend). В CI — http://127.0.0.1:8000.
 * Прод: PLAYWRIGHT_API_URL = https://bt-aistudio.ru (nginx проксирует /concierge/api/)
 */
const apiBase = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'
const BOT_USERNAME = process.env.PLAYWRIGHT_BOT_USERNAME || 'test_bot'
const isSameOrigin =
  process.env.PLAYWRIGHT_BASE_URL && !/localhost|127\.0\.0\.1/.test(process.env.PLAYWRIGHT_BASE_URL)
const WEBHOOK_URL = isSameOrigin
  ? `${process.env.PLAYWRIGHT_BASE_URL!.replace(/\/$/, '')}/concierge/api/v1/webhook/${BOT_USERNAME}`
  : `${apiBase.replace(/\/$/, '')}/api/v1/webhook/${BOT_USERNAME}`

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
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Bot-Api-Secret-Token': process.env.PLAYWRIGHT_WEBHOOK_SECRET || 'e2e-webhook-secret',
      },
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
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Bot-Api-Secret-Token': process.env.PLAYWRIGHT_WEBHOOK_SECRET || 'e2e-webhook-secret',
      },
    })

    if (res1.status() === 403) test.skip(true, 'Webhook secret required')

    expect(res1.status()).toBe(200)

    const res2 = await request.post(WEBHOOK_URL, {
      data: update,
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Bot-Api-Secret-Token': process.env.PLAYWRIGHT_WEBHOOK_SECRET || 'e2e-webhook-secret',
      },
    })
    expect(res2.status()).toBe(200)
    const body = await res2.json()
    expect(body.msg).toBe('already_processed')
  })
})
