# Appointments WebSocket Event Contract

Контракт WS-событий для live updates Kanban board. Фиксирует канал, формат события и правила обработки.

---

## 1. Канал

```
appointments_updates:{tenant_id}
```

Пример: `appointments_updates:1` для tenant с id=1.

---

## 2. Событие

При изменении статуса записи публикуется:

```json
{
  "type": "appointment_status_updated",
  "appointment_id": 123,
  "old_status": "new",
  "new_status": "confirmed"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `type` | string | Всегда `"appointment_status_updated"` |
| `appointment_id` | int | ID записи |
| `old_status` | string | Предыдущий статус (new, confirmed, in_progress, completed, waitlist, cancelled, no_show) |
| `new_status` | string | Новый статус после перехода |

---

## 3. Правила

- **Tenant isolation:** события публикуются только в канал своего tenant. Клиент подписывается на `appointments_updates:{tenant_id}` и получает только события своего tenant.

- **Terminal переходы (cancelled, no_show):** событие уходит в WS, но запись должна **исчезнуть из Kanban** (переместиться в Terminal block). Kanban не включает terminal статусы.

- **Переходы между Kanban-колонками:** при смене статуса между waitlist / new / confirmed / in_progress / completed запись должна **перемещаться между колонками** Kanban без перезагрузки всей доски.

- **Порядок публикации:** событие публикуется **только после успешного `db.commit()`**. При ошибке коммита событие не отправляется.

---

## 4. Источник

Событие публикуется из:

```
PATCH /api/v1/appointments/{id}/status
```

При успешном изменении статуса записи endpoint выполняет commit и публикует payload в Redis channel `appointments_updates:{tenant_id}`. Подписчики (WebSocket gateway) получают событие и обновляют UI.
