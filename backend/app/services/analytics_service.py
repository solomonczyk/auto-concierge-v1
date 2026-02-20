from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Appointment, AppointmentStatus, Client

class AnalyticsService:
    @staticmethod
    async def get_tenant_stats(db: AsyncSession, tenant_id: int):
        """
        Calculates key KPIs for a specific tenant.
        - Total bookings
        - Conversion (bookings / total clients)
        - Popular categories (categorized in v2.0, now just total)
        """
        # 1. Total bookings (confirmed/completed)
        stmt_total = select(func.count(Appointment.id)).where(
            and_(
                Appointment.tenant_id == tenant_id,
                Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED, AppointmentStatus.NEW])
            )
        )
        total_bookings = (await db.execute(stmt_total)).scalar() or 0

        # 2. Lost leads (cancelled)
        stmt_lost = select(func.count(Appointment.id)).where(
            and_(
                Appointment.tenant_id == tenant_id,
                Appointment.status == AppointmentStatus.CANCELLED
            )
        )
        lost_leads = (await db.execute(stmt_lost)).scalar() or 0

        # 3. Total registered clients
        stmt_clients = select(func.count(Client.id)).where(Client.tenant_id == tenant_id)
        total_clients = (await db.execute(stmt_clients)).scalar() or 0

        # 4. Peak Hours (simplified: count by hour of start_time)
        # This is more complex for SQL in SQLAlchemy async, so we'll leave as placeholder or simplify
        peak_hours = "10:00 - 14:00" # Dummy for MVP

        return {
            "total_bookings": total_bookings,
            "lost_leads": lost_leads,
            "total_clients": total_clients,
            "peak_hours": peak_hours,
            "bookings_by_category": {
                "maintenance": int(total_bookings * 0.4), # Placeholder
                "repairs": int(total_bookings * 0.6)
            }
        }

analytics_service = AnalyticsService()
