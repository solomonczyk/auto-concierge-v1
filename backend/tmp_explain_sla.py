"""Run EXPLAIN ANALYZE for SLA query. Requires PostgreSQL running (docker-compose up -d db)."""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    import asyncpg
    host = os.getenv("POSTGRES_SERVER", "localhost")
    if host == "db":
        host = "localhost"
    port = 5435 if host == "localhost" else 5432
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "autoservice")
    conn = await asyncpg.connect(host=host, port=port, user=user, password=password, database=dbname)
    try:
        rows = await conn.fetch("""
            EXPLAIN (ANALYZE, FORMAT TEXT)
            SELECT *
            FROM appointments
            WHERE tenant_id = 1
            AND status = 'new'
            ORDER BY created_at ASC
            LIMIT 50;
        """)
        for r in rows:
            print(r["QUERY PLAN"])
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
