from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Enum as SQLEnum, JSON, BigInteger
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.session import Base

class AppointmentStatus(str, Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    WAITLIST = "waitlist"

class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"

class Tariff(str, Enum):
    FREE = "free"
    STANDARD = "standard"
    PRO = "pro"

class UserRole(str, Enum):
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

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
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
    car_make: Mapped[Optional[str]] = mapped_column(String(100))
    car_year: Mapped[Optional[int]] = mapped_column(Integer)
    vin: Mapped[Optional[str]] = mapped_column(String(17))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="clients")
    appointments: Mapped[List["Appointment"]] = relationship("Appointment", back_populates="client")

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
    notes: Mapped[Optional[str]] = mapped_column(Text)
    # Vehicle info collected at booking
    car_make: Mapped[Optional[str]] = mapped_column(String(100))   # e.g. "Toyota Camry"
    car_year: Mapped[Optional[int]] = mapped_column(Integer)       # e.g. 2019
    vin: Mapped[Optional[str]] = mapped_column(String(17))         # 17-char VIN
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="appointments")
    shop: Mapped["Shop"] = relationship("Shop", back_populates="appointments")
    client: Mapped["Client"] = relationship("Client", back_populates="appointments")
    service: Mapped["Service"] = relationship("Service", back_populates="appointments")
