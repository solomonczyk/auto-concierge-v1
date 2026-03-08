from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.db.session import get_db
from app.models.models import Appointment, AuditLog, Client, User, UserRole
from app.schemas.audit_log import AuditLogListResponse, AuditLogRead
from app.schemas.deleted_record import (
    DeletedAppointmentListResponse,
    DeletedAppointmentRead,
    DeletedClientListResponse,
    DeletedClientRead,
)

router = APIRouter()


def _resolve_tenant_scope(*, current_user: User, model_tenant_id, tenant_id: Optional[int] = None) -> list:
    filters = []

    if current_user.role != UserRole.SUPERADMIN:
        if current_user.tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin user must belong to a tenant",
            )
        if tenant_id is not None and tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant filter is outside your scope",
            )
        filters.append(model_tenant_id == current_user.tenant_id)
        return filters

    if tenant_id is not None:
        filters.append(model_tenant_id == tenant_id)

    return filters


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def read_audit_logs(
    tenant_id: Optional[int] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.require_role([UserRole.ADMIN, UserRole.SUPERADMIN])),
) -> AuditLogListResponse:
    filters = _resolve_tenant_scope(
        current_user=current_user,
        model_tenant_id=AuditLog.tenant_id,
        tenant_id=tenant_id,
    )

    if entity_type:
        filters.append(AuditLog.entity_type == entity_type.strip().lower())
    if action:
        filters.append(AuditLog.action == action.strip().lower())
    if date_from:
        filters.append(AuditLog.created_at >= date_from)
    if date_to:
        filters.append(AuditLog.created_at <= date_to)

    if filters:
        where_clause = and_(*filters)
        items_stmt = select(AuditLog).where(where_clause)
        total_stmt = select(func.count()).select_from(AuditLog).where(where_clause)
    else:
        items_stmt = select(AuditLog)
        total_stmt = select(func.count()).select_from(AuditLog)

    items_stmt = items_stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)

    total_result = await db.execute(total_stmt)
    items_result = await db.execute(items_stmt)

    return AuditLogListResponse(
        items=list(items_result.scalars().all()),
        total=total_result.scalar_one(),
        limit=limit,
        offset=offset,
    )


@router.get("/deleted/appointments", response_model=DeletedAppointmentListResponse)
async def read_deleted_appointments(
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.require_role([UserRole.ADMIN, UserRole.SUPERADMIN])),
) -> DeletedAppointmentListResponse:
    filters = _resolve_tenant_scope(
        current_user=current_user,
        model_tenant_id=Appointment.tenant_id,
    )
    filters.append(Appointment.deleted_at.is_not(None))

    if date_from:
        filters.append(Appointment.deleted_at >= date_from)
    if date_to:
        filters.append(Appointment.deleted_at <= date_to)

    where_clause = and_(*filters)
    items_stmt = (
        select(Appointment)
        .where(where_clause)
        .order_by(Appointment.deleted_at.desc())
        .offset(offset)
        .limit(limit)
    )
    total_stmt = select(func.count()).select_from(Appointment).where(where_clause)

    total_result = await db.execute(total_stmt)
    items_result = await db.execute(items_stmt)

    return DeletedAppointmentListResponse(
        items=list(items_result.scalars().all()),
        total=total_result.scalar_one(),
        limit=limit,
        offset=offset,
    )


@router.get("/deleted/clients", response_model=DeletedClientListResponse)
async def read_deleted_clients(
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.require_role([UserRole.ADMIN, UserRole.SUPERADMIN])),
) -> DeletedClientListResponse:
    filters = _resolve_tenant_scope(
        current_user=current_user,
        model_tenant_id=Client.tenant_id,
    )
    filters.append(Client.deleted_at.is_not(None))

    if date_from:
        filters.append(Client.deleted_at >= date_from)
    if date_to:
        filters.append(Client.deleted_at <= date_to)

    where_clause = and_(*filters)
    items_stmt = (
        select(Client)
        .where(where_clause)
        .order_by(Client.deleted_at.desc())
        .offset(offset)
        .limit(limit)
    )
    total_stmt = select(func.count()).select_from(Client).where(where_clause)

    total_result = await db.execute(total_stmt)
    items_result = await db.execute(items_stmt)

    return DeletedClientListResponse(
        items=list(items_result.scalars().all()),
        total=total_result.scalar_one(),
        limit=limit,
        offset=offset,
    )
