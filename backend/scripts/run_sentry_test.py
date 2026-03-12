#!/usr/bin/env python3
"""
Run Sentry test: login, call GET /api/v1/_sentry-test, report.
Uses .env for SENTRY_DSN. Requires backend deps (DB, Redis) or use test DB.
"""
import asyncio
import os
import sys

# Load .env before importing app
from pathlib import Path
_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env)

# Ensure ENVIRONMENT=development for endpoint to work
os.environ.setdefault("ENVIRONMENT", "development")

# Use test DB for standalone run (no docker)
os.environ.setdefault("POSTGRES_SERVER", "localhost")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
os.environ.setdefault("POSTGRES_DB", "autoservice")
os.environ.setdefault("REDIS_HOST", "localhost")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main():
    from httpx import AsyncClient
    from app.main import app
    from app.core.config import settings

    dsn = getattr(settings, "SENTRY_DSN", None) or os.getenv("SENTRY_DSN")
    if not dsn:
        print("SENTRY_DSN not set in .env or environment. Cannot run test.")
        sys.exit(1)

    async with AsyncClient(app=app, base_url="http://test") as client:
        # Login
        r = await client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={"username": "admin", "password": "admin"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        if r.status_code != 200:
            print(f"Login failed: {r.status_code}")
            sys.exit(1)
        csrf = r.cookies.get("csrf_token")
        if csrf:
            client.headers["X-CSRF-Token"] = csrf

        # Call _sentry-test
        r2 = await client.get(f"{settings.API_V1_STR}/_sentry-test")
        print(f"Endpoint response: {r2.status_code}")
        if r2.status_code == 500:
            print("ValueError raised as expected. Check Sentry dashboard for event and tenant_id tag.")
        elif r2.status_code == 404:
            print("Endpoint disabled (production?). Set ENVIRONMENT=development.")
        else:
            print(f"Unexpected: {r2.text[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
