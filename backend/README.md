# Backend

## Postgres password drift with persisted volume

If PostgreSQL uses an existing named volume, changing `POSTGRES_PASSWORD` in `.env` / `docker-compose.yml` does not rotate the actual DB user password automatically.

Symptom:
- backend gets `asyncpg.exceptions.InvalidPasswordError`
- `/health` returns DB unavailable
- DSN in app settings may still look correct

Fix:
- either rotate password inside PostgreSQL explicitly:
  `ALTER USER postgres WITH PASSWORD '...';`
- or recreate the Postgres data volume if data reset is acceptable

Current project note:
- service `db` uses named volume `postgres_data`
