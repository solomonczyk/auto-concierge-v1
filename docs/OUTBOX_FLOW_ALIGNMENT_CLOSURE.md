# Outbox Flow Alignment — Closure

All appointment mutation flows now use transactional outbox for external integration:

- `POST /appointments` → outbox
- `PATCH /appointments/{id}` → outbox
- `PATCH /appointments/{id}/status` → outbox
- `PUT /appointments/{id}` → outbox
- `POST /public/...` create → outbox
- `POST /public/...` reschedule/update → outbox

**No direct external integration calls remain in API layer.**
