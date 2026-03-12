"""
Appointment snapshot read-model service.

Reads and normalizes appointment data into a canonical snapshot.
Does NOT contain business logic — pure read-model assembly.

Snapshot is the SOURCE OF TRUTH for reading appointment data.
New features (reschedule, cancel, reminder redesign, support views) should use
get_appointment_snapshot() instead of ad-hoc assembly from other endpoints.
"""

from typing import List, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.models import Appointment, AppointmentHistory, Client
from app.services.appointment_lifecycle_rules import (
    can_cancel_appointment,
    can_reschedule_appointment,
)
from app.schemas.appointment_snapshot import (
    AppointmentSnapshotClient,
    AppointmentSnapshotResponse,
    AppointmentSnapshotService,
    AppointmentSnapshotShop,
    AppointmentSnapshotIntake,
    PublicAppointmentListPage,
)

# Normalized source mapping (DB value -> contract value)
_SOURCE_MAP = {
    "public": "WEBAPP",
    "dashboard": "DASHBOARD",
    "api": "API",
    "bot": "BOT",
    "system": "SYSTEM",
}

_NOT_DELETED = Appointment.deleted_at.is_(None)


def _normalize_source(raw: str | None) -> str:
    if not raw:
        return "API"
    return _SOURCE_MAP.get(raw.lower(), raw.upper())


def _build_snapshot_from_appt(
    appt: Appointment,
    source: str,
) -> AppointmentSnapshotResponse:
    """Build snapshot from an already-loaded Appointment. No DB access."""
    client = None
    if appt.client:
        client = AppointmentSnapshotClient(
            id=appt.client.id,
            name=appt.client.full_name or "",
            phone=appt.client.phone,
        )
    service = None
    if appt.service:
        service = AppointmentSnapshotService(
            id=appt.service.id,
            name=appt.service.name,
        )
    shop = None
    if appt.shop:
        shop = AppointmentSnapshotShop(
            id=appt.shop.id,
            name=appt.shop.name,
        )
    intake = None
    if appt.intake:
        intake = AppointmentSnapshotIntake(status=appt.intake.status)
    return AppointmentSnapshotResponse(
        appointment_id=appt.id,
        tenant_id=appt.tenant_id,
        status=appt.status.value.upper(),
        start_time=appt.start_time,
        end_time=appt.end_time,
        client=client,
        service=service,
        shop=shop,
        intake=intake,
        source=source,
        is_waitlist=(appt.status.value == "waitlist"),
        can_reschedule=can_reschedule_appointment(status=appt.status),
        can_cancel=can_cancel_appointment(status=appt.status),
    )


async def get_appointment_snapshot(
    db: AsyncSession,
    appointment_id: int,
    tenant_id: int,
) -> AppointmentSnapshotResponse | None:
    """
    Build canonical appointment snapshot for read-model consumers.
    Returns None if appointment not found or belongs to another tenant.
    """
    stmt = (
        select(Appointment)
        .options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
            joinedload(Appointment.shop),
            selectinload(Appointment.intake),
        )
        .where(
            Appointment.id == appointment_id,
            Appointment.tenant_id == tenant_id,
            _NOT_DELETED,
        )
    )
    result = await db.execute(stmt)
    appt = result.unique().scalar_one_or_none()
    if not appt:
        return None

    # Source from first history record
    hist_stmt = (
        select(AppointmentHistory.source)
        .where(AppointmentHistory.appointment_id == appointment_id)
        .order_by(AppointmentHistory.created_at.asc())
        .limit(1)
    )
    hist_result = await db.execute(hist_stmt)
    row = hist_result.one_or_none()
    raw_source = row[0] if row else None
    source = _normalize_source(raw_source)
    return _build_snapshot_from_appt(appt, source)


async def get_appointment_snapshots_for_client(
    db: AsyncSession,
    tenant_id: int,
    client_id: int,
    *,
    limit: int = 50,
    offset: int = 0,
) -> List[AppointmentSnapshotResponse]:
    """
    Bulk fetch appointment snapshots for a client. No N+1: one query for
    appointments with relations, one for first history per appointment.
    """
    stmt = (
        select(Appointment)
        .options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
            joinedload(Appointment.shop),
            selectinload(Appointment.intake),
        )
        .where(
            Appointment.client_id == client_id,
            Appointment.tenant_id == tenant_id,
            _NOT_DELETED,
        )
        .order_by(Appointment.start_time)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    appts = list(result.unique().scalars().all())
    if not appts:
        return []

    appt_ids = [a.id for a in appts]
    hist_stmt = (
        select(AppointmentHistory.appointment_id, AppointmentHistory.source)
        .where(AppointmentHistory.appointment_id.in_(appt_ids))
        .order_by(AppointmentHistory.created_at.asc())
    )
    hist_result = await db.execute(hist_stmt)
    hist_rows = hist_result.all()
    first_source: dict[int, str] = {}
    for appt_id, raw_src in hist_rows:
        if appt_id not in first_source:
            first_source[appt_id] = _normalize_source(raw_src)

    return [
        _build_snapshot_from_appt(appt, first_source.get(appt.id, "API"))
        for appt in appts
    ]


async def get_public_appointment_snapshots_by_telegram_id(
    db: AsyncSession,
    tenant_id: int,
    telegram_id: int,
    *,
    limit: int = 50,
    offset: int = 0,
) -> Optional[PublicAppointmentListPage]:
    """
    List appointment snapshots for client identified by telegram_id in tenant.
    Returns None if client not found (caller should 404).
    """
    stmt = select(Client).where(
        and_(
            Client.telegram_id == telegram_id,
            Client.tenant_id == tenant_id,
            Client.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    if not client:
        return None

    count_stmt = (
        select(func.count())
        .select_from(Appointment)
        .where(
            Appointment.client_id == client.id,
            Appointment.tenant_id == tenant_id,
            _NOT_DELETED,
        )
    )
    total = (await db.execute(count_stmt)).scalar_one()

    items = await get_appointment_snapshots_for_client(
        db, tenant_id, client.id, limit=limit, offset=offset
    )
    has_more = offset + len(items) < total

    return PublicAppointmentListPage(
        items=items,
        limit=limit,
        offset=offset,
        total=total,
        has_more=has_more,
    )
