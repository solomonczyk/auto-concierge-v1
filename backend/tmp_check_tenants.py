"""Quick tenant/appointment check."""
import asyncio
from sqlalchemy import select
from app.db.session import async_session_local
from app.models.models import User, Appointment

async def main():
    async with async_session_local() as db:
        users = (await db.execute(select(User.username, User.tenant_id))).all()
        print("Users (username, tenant_id):", users)
        apps = (await db.execute(select(Appointment.id, Appointment.tenant_id, Appointment.status).order_by(Appointment.id.desc()).limit(10))).all()
        print("Appointments (id, tenant_id, status):", apps)

if __name__ == "__main__":
    asyncio.run(main())
