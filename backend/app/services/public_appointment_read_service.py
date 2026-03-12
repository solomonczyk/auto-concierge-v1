"""
Public appointment read orchestration service.

Goal: keep API routes thin and centralize public self-service read flow:
- access validation (telegram_id binding within tenant scope)
- snapshot retrieval via canonical snapshot builder

This module is part of Client Self-Service Read Layer (public flow).
"""

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Appointment, Client
from app.schemas.appointment_snapshot import AppointmentSnapshotResponse
from app.services.appointment_snapshot_service import get_appointment_snapshot


async def _require_public_appointment_access(
    *,
    db: AsyncSession,
    tenant_id: int,
    appointment_id: int,
    telegram_id: int,
) -> None:
    """
    Public access validator.

    Proof of access: Telegram user binding (telegram_id) + tenant context (slug).
    """
    stmt = (
        select(Appointment.id, Client.telegram_id)
        .join(Client, Appointment.client_id == Client.id)
        .where(
            and_(
                Appointment.id == appointment_id,
                Appointment.tenant_id == tenant_id,
                Appointment.deleted_at.is_(None),
                Client.tenant_id == tenant_id,
                Client.deleted_at.is_(None),
            )
        )
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    if int(row.telegram_id or 0) != int(telegram_id):
        raise HTTPException(status_code=403, detail="Нет доступа к записи")


async def get_public_appointment_snapshot(
    *,
    db: AsyncSession,
    tenant_id: int,
    appointment_id: int,
    telegram_id: int,
) -> AppointmentSnapshotResponse | None:
    """
    Single appointment snapshot read for public self-service flow.

    - validates access via `_require_public_appointment_access`
    - returns canonical snapshot via `get_appointment_snapshot`
    """
    await _require_public_appointment_access(
        db=db,
        tenant_id=tenant_id,
        appointment_id=appointment_id,
        telegram_id=telegram_id,
    )

    return await get_appointment_snapshot(db, appointment_id, tenant_id)

