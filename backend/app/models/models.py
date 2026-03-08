from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.models.auto_extensions import ClientAutoProfile, AppointmentAutoSnapshot
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Enum as SQLEnum, JSON, BigInteger, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.session import Base

class AppointmentStatus(str, Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    WAITLIST = "waitlist"

class TenantStatus(str, Enum):
    ACTIVE = "active"
    TRIAL = "trial"
    SUSPENDED = "suspended"
    DELETED = "deleted"
    PENDING = "pending"


class IntegrationStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"

class Tariff(str, Enum):
    FREE = "free"
    STANDARD = "standard"
    PRO = "pro"

class UserRole(str, Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    MANAGER = "manager"
    STAFF = "staff"

class TariffPlan(Base):
    __tablename__ = "tariff_plans"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True) # free, standard, pro
    max_appointments: Mapped[int] = mapped_column(Integer, default=10)
    max_shops: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(default=True)
    
    tenants: Mapped[List["Tenant"]] = relationship("Tenant", back_populates="tariff_plan")

class Tenant(Base):
    __tablename__ = "tenants"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)
    # Stored encrypted
    encrypted_bot_token: Mapped[Optional[str]] = mapped_column(String(500), unique=True, nullable=True)
    # Hashed for fast lookups
    bot_token_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True, unique=True, nullable=True)
    settings_json: Mapped[dict] = mapped_column(JSON, default={})
    
    tariff_plan_id: Mapped[int] = mapped_column(ForeignKey("tariff_plans.id"), nullable=True)
    tariff_plan: Mapped["TariffPlan"] = relationship("TariffPlan", back_populates="tenants")
    
    status: Mapped[TenantStatus] = mapped_column(SQLEnum(TenantStatus), default=TenantStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    users: Mapped[List["User"]] = relationship("User", back_populates="tenant")
    shops: Mapped[List["Shop"]] = relationship("Shop", back_populates="tenant")
    clients: Mapped[List["Client"]] = relationship("Client", back_populates="tenant")
    services: Mapped[List["Service"]] = relationship("Service", back_populates="tenant")
    appointments: Mapped[List["Appointment"]] = relationship("Appointment", back_populates="tenant")
    settings: Mapped[Optional["TenantSettings"]] = relationship("TenantSettings", back_populates="tenant", uselist=False)

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.STAFF, nullable=False)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    shop_id: Mapped[Optional[int]] = mapped_column(ForeignKey("shops.id"), nullable=True)
    shop: Mapped[Optional["Shop"]] = relationship("Shop", back_populates="users")

class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="shops")
    appointments: Mapped[List["Appointment"]] = relationship("Appointment", back_populates="shop")
    users: Mapped[List["User"]] = relationship("User", back_populates="shop")

class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="clients")
    appointments: Mapped[List["Appointment"]] = relationship("Appointment", back_populates="client")
    auto_profile: Mapped[Optional["ClientAutoProfile"]] = relationship(
        "ClientAutoProfile",
        back_populates="client",
        uselist=False,
        lazy="selectin",
    )


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    base_price: Mapped[float] = mapped_column(Float)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="services")
    appointments: Mapped[List["Appointment"]] = relationship("Appointment", back_populates="service")

class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(SQLEnum(AppointmentStatus), default=AppointmentStatus.NEW, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    integration_status: Mapped[IntegrationStatus] = mapped_column(
        SQLEnum(IntegrationStatus),
        default=IntegrationStatus.SUCCESS,
        nullable=False,
    )
    last_integration_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_integration_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="appointments")
    shop: Mapped["Shop"] = relationship("Shop", back_populates="appointments")
    client: Mapped["Client"] = relationship("Client", back_populates="appointments")
    service: Mapped["Service"] = relationship("Service", back_populates="appointments")
    history: Mapped[List["AppointmentHistory"]] = relationship("AppointmentHistory", back_populates="appointment", lazy="dynamic")
    auto_snapshot: Mapped[Optional["AppointmentAutoSnapshot"]] = relationship(
        "AppointmentAutoSnapshot",
        back_populates="appointment",
        uselist=False,
        lazy="selectin",
    )


class AppointmentHistory(Base):
    """Immutable audit log of every appointment status change."""
    __tablename__ = "appointment_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    old_status: Mapped[str] = mapped_column(String(20), nullable=False)
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="api")
    reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    appointment: Mapped["Appointment"] = relationship("Appointment", back_populates="history")


class TenantSettings(Base):
    """Per-tenant working hours and slot configuration."""
    __tablename__ = "tenant_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), unique=True, nullable=False, index=True)
    work_start: Mapped[int] = mapped_column(Integer, default=9)    # hour 0-23
    work_end: Mapped[int] = mapped_column(Integer, default=18)     # hour 0-23
    slot_duration: Mapped[int] = mapped_column(Integer, default=30) # minutes
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="settings")


class AuditLog(Base):
    """Universal audit log for entity changes. Minimal scope: appointments, clients, auth."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # create, update, soft_delete
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # appointment, client, tenant_settings, auth
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # id as string for flexibility
    payload_before: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    payload_after: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="api")  # api, dashboard, bot, system
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_events_status_available_at", "status", "available_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


# Ensure ClientAutoProfile is in registry for relationship resolution
import app.models.auto_extensions  # noqa: F401
