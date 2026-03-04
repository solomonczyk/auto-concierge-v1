"""
Create the platform SUPERADMIN user (no tenant, global access).

Usage inside Docker:
  docker exec -it autoservice_api_prod python scripts/create_superadmin.py \
      --username root --password strongpassword

Usage locally (with PYTHONPATH set):
  cd backend
  PYTHONPATH=. python scripts/create_superadmin.py --username root --password strongpassword
"""
import argparse
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.session import async_session_local
from app.models.models import User, UserRole
from app.core.security import get_password_hash


async def create_superadmin(username: str, password: str) -> None:
    async with async_session_local() as db:
        existing = await db.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none():
            print(f"[ERROR] User '{username}' already exists. Aborting.")
            sys.exit(1)

        user = User(
            tenant_id=None,
            username=username,
            hashed_password=get_password_hash(password),
            role=UserRole.SUPERADMIN,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    print(f"[OK] SUPERADMIN created: id={user.id} username={username}")
    print(f"     Login at POST /api/v1/login/access-token")
    print(f"     JWT will contain: role=superadmin, tenant_id=null")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create platform SUPERADMIN user")
    parser.add_argument("--username", required=True, help="Superadmin username")
    parser.add_argument("--password", required=True, help="Superadmin password (min 8 chars)")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("[ERROR] Password must be at least 8 characters.")
        sys.exit(1)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(create_superadmin(args.username, args.password))


if __name__ == "__main__":
    main()
