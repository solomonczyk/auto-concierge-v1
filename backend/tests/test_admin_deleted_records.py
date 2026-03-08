from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.models import (
    Appointment,
    AppointmentStatus,
    Client,
    Service,
    Shop,
    Tenant,
    TenantStatus,
    User,
    UserRole,
)


@pytest.mark.asyncio
async def test_admin_reads_deleted_clients_sorted_and_scoped(
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
    own_deleted_new = Client(
        tenant_id=1,
        full_name="Deleted New",
        phone="+79990000001",
        deleted_at=now,
        deleted_by=1,
    )
    own_deleted_old = Client(
        tenant_id=1,
        full_name="Deleted Old",
        phone="+79990000002",
        deleted_at=now - timedelta(hours=1),
        deleted_by=1,
    )
    foreign_deleted = Client(
        tenant_id=2,
        full_name="Foreign Deleted",
        phone="+79990000003",
        deleted_at=now,
        deleted_by=None,
    )

    db_session.add(other_tenant)
    db_session.add_all([own_deleted_new, own_deleted_old, foreign_deleted])
    await db_session.commit()

    response = await client_auth.get(
        "/api/v1/admin/deleted/clients",
        params={
            "date_from": (now - timedelta(hours=2)).isoformat(),
            "date_to": (now + timedelta(minutes=1)).isoformat(),
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
    assert payload["items"][0]["full_name"] == "Deleted Old"
    assert payload["items"][0]["tenant_id"] == 1


@pytest.mark.asyncio
async def test_admin_reads_deleted_appointments_only_for_own_tenant(
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
    other_shop = Shop(tenant_id=2, name="Other Shop", address="Address", phone="+79990000011")
    other_service = Service(tenant_id=2, name="Other Service", duration_minutes=30, base_price=1000.0)
    other_client = Client(tenant_id=2, full_name="Other Client", phone="+79990000012")
    own_deleted_new = Appointment(
        tenant_id=1,
        shop_id=1,
        client_id=1,
        service_id=1,
        start_time=now,
        end_time=now + timedelta(hours=1),
        status=AppointmentStatus.CANCELLED,
        deleted_at=now,
        deleted_by=1,
    )
    own_deleted_old = Appointment(
        tenant_id=1,
        shop_id=1,
        client_id=1,
        service_id=1,
        start_time=now - timedelta(days=1),
        end_time=now - timedelta(days=1) + timedelta(hours=1),
        status=AppointmentStatus.NO_SHOW,
        deleted_at=now - timedelta(hours=1),
        deleted_by=1,
    )

    db_session.add(other_tenant)
    db_session.add(other_shop)
    await db_session.flush()
    db_session.add(other_service)
    db_session.add(other_client)
    await db_session.flush()

    foreign_deleted = Appointment(
        tenant_id=2,
        shop_id=other_shop.id,
        client_id=other_client.id,
        service_id=other_service.id,
        start_time=now,
        end_time=now + timedelta(hours=1),
        status=AppointmentStatus.CANCELLED,
        deleted_at=now,
        deleted_by=None,
    )

    db_session.add(own_deleted_new)
    db_session.add(own_deleted_old)
    db_session.add(foreign_deleted)
    await db_session.commit()

    response = await client_auth.get(
        "/api/v1/admin/deleted/appointments",
        params={
            "date_from": (now - timedelta(hours=2)).isoformat(),
            "date_to": (now + timedelta(minutes=1)).isoformat(),
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
    assert payload["items"][0]["status"] == AppointmentStatus.NO_SHOW.value


@pytest.mark.asyncio
async def test_superadmin_reads_deleted_clients_across_tenants(
    client: AsyncClient,
    db_session: AsyncSession,
):
    now = datetime.now(timezone.utc)

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
    foreign_deleted = Client(
        tenant_id=2,
        full_name="Ghost Client",
        phone="+79990000013",
        deleted_at=now,
        deleted_by=None,
    )

    db_session.add(other_tenant)
    db_session.add(superadmin)
    db_session.add(foreign_deleted)
    await db_session.commit()

    login_response = await client.post(
        "/api/v1/login/access-token",
        data={"username": "root", "password": "rootpass"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert login_response.status_code == 200

    response = await client.get(
        "/api/v1/admin/deleted/clients",
        params={"limit": 10, "offset": 0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert payload["limit"] == 10
    assert payload["offset"] == 0
    assert any(item["tenant_id"] == 2 for item in payload["items"])
    assert any(item["full_name"] == "Ghost Client" for item in payload["items"])
