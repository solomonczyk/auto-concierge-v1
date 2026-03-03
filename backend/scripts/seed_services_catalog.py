"""
Seed services from catalog of 100 most common auto services.
Usage: python -m scripts.seed_services_catalog [--tenant-id 3] [--dry-run]
"""
import asyncio
import argparse
import json
import os
import sys

# Add project root for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import async_session_local
from app.models.models import Service
from app.core.config import settings
from sqlalchemy import select


CATALOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "services_catalog_100.json")


async def seed_catalog(tenant_id: int, dry_run: bool = False) -> int:
    """Load catalog and insert services for tenant. Returns count of added services."""
    with open(CATALOG_PATH, encoding="utf-8") as f:
        catalog = json.load(f)

    added = 0
    async with async_session_local() as db:
        result = await db.execute(select(Service).where(Service.tenant_id == tenant_id))
        existing = {s.name for s in result.scalars().all()}

        for item in catalog:
            name = item["name"]
            if name in existing:
                continue
            if dry_run:
                pass  # Just count, no per-item print (encoding issues on Windows)
                added += 1
                continue
            svc = Service(
                tenant_id=tenant_id,
                name=name,
                base_price=float(item["price"]),
                duration_minutes=item["duration"],
            )
            db.add(svc)
            existing.add(name)
            added += 1

        if not dry_run and added:
            await db.commit()
    return added


def main():
    parser = argparse.ArgumentParser(description="Seed services from 100-item catalog")
    parser.add_argument("--tenant-id", type=int, default=None, help="Tenant ID (default: PUBLIC_TENANT_ID or 3)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be added, don't commit")
    args = parser.parse_args()
    tenant_id = args.tenant_id or getattr(settings, "PUBLIC_TENANT_ID", None) or 3

    if not os.path.exists(CATALOG_PATH):
        print(f"Catalog not found: {CATALOG_PATH}")
        sys.exit(1)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    added = asyncio.run(seed_catalog(tenant_id, args.dry_run))
    mode = "(dry-run)" if args.dry_run else ""
    print(f"Done {mode}: {added} new services added for tenant_id={tenant_id}")


if __name__ == "__main__":
    main()
