from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.models import AuditLog, Tenant, TenantStatus, User, UserRole


@pytest.mark.asyncio
async def test_admin_audit_logs_filters_by_scope_and_fields(
    client_auth: AsyncClient,
    db_session: AsyncSession,
):
    now = datetime.now(timezone.utc)

    other_tenant = Tenant(
        id=2,
        name="Other Tenant",
        status=TenantStatus.ACTIVE,
        tariff_plan_id=1,
    )
    db_session.add(other_tenant)
    await db_session.flush()

    db_session.add_all(
        [
            AuditLog(
                tenant_id=1,
                actor_user_id=1,
                action="create",
                entity_type="appointment",
                entity_id="11",
                payload_after={"status": "new"},
                source="api",
                created_at=now - timedelta(minutes=40),
            ),
            AuditLog(
                tenant_id=1,
                actor_user_id=1,
                action="create",
                entity_type="appointment",
                entity_id="12",
                payload_after={"status": "confirmed"},
                source="api",
                created_at=now - timedelta(hours=1, minutes=10),
            ),
            AuditLog(
                tenant_id=1,
                actor_user_id=1,
                action="update",
                entity_type="client",
                entity_id="21",
                payload_after={"phone": "+79990000000"},
                source="api",
                created_at=now,
            ),
            AuditLog(
                tenant_id=2,
                actor_user_id=None,
                action="create",
                entity_type="appointment",
                entity_id="31",
                payload_after={"status": "new"},
                source="system",
                created_at=now,
            ),
        ]
    )
    await db_session.commit()

    response = await client_auth.get(
        "/api/v1/admin/audit-logs",
        params={
            "entity_type": "appointment",
            "action": "create",
            "date_from": (now - timedelta(hours=2)).isoformat(),
            "date_to": (now - timedelta(minutes=20)).isoformat(),
            "limit": 1,
            "offset": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["limit"] == 1
    assert payload["offset"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["tenant_id"] == 1
    assert payload["items"][0]["entity_type"] == "appointment"
    assert payload["items"][0]["action"] == "create"
    assert payload["items"][0]["entity_id"] == "12"


@pytest.mark.asyncio
async def test_admin_audit_logs_rejects_foreign_tenant_filter(
    client_auth: AsyncClient,
    db_session: AsyncSession,
):
    other_tenant = Tenant(
        id=2,
        name="Other Tenant",
        status=TenantStatus.ACTIVE,
        tariff_plan_id=1,
    )
    db_session.add(other_tenant)
    await db_session.commit()

    response = await client_auth.get(
        "/api/v1/admin/audit-logs",
        params={"tenant_id": 2},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_superadmin_audit_logs_can_filter_any_tenant(
    client: AsyncClient,
    db_session: AsyncSession,
):
    other_tenant = Tenant(
        id=2,
        name="Other Tenant",
        status=TenantStatus.ACTIVE,
        tariff_plan_id=1,
    )
    superadmin = User(
        username="root",
        hashed_password=get_password_hash("rootpass"),
        is_active=True,
        role=UserRole.SUPERADMIN,
        tenant_id=None,
        shop_id=None,
    )
    db_session.add(other_tenant)
    db_session.add(superadmin)
    db_session.add(
        AuditLog(
            tenant_id=2,
            actor_user_id=None,
            action="soft_delete",
            entity_type="client",
            entity_id="91",
            payload_before={"full_name": "Ghost Client"},
            source="api",
        )
    )
    await db_session.commit()

    login_response = await client.post(
        "/api/v1/login/access-token",
        data={"username": "root", "password": "rootpass"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert login_response.status_code == 200

    response = await client.get(
        "/api/v1/admin/audit-logs",
        params={"tenant_id": 2, "entity_type": "client", "limit": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["limit"] == 5
    assert payload["offset"] == 0
    assert len(payload["items"]) == 1
    assert payload["items"][0]["tenant_id"] == 2
    assert payload["items"][0]["action"] == "soft_delete"
