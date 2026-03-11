from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.db.session import Base


class WebhookProvisioningStatus:
    """Operational state for Telegram webhook provisioning."""

    NOT_CONFIGURED = "not_configured"
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"

    VALUES = (NOT_CONFIGURED, PENDING, ACTIVE, FAILED)


class TelegramBot(Base):
    __tablename__ = "telegram_bots"

    id = Column(Integer, primary_key=True)

    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    bot_token = Column(String, nullable=False, unique=True)
    bot_username = Column(String, nullable=True)
    webhook_secret = Column(String(256), nullable=True)

    # Webhook provisioning operational state
    webhook_status = Column(
        String(32),
        nullable=False,
        default=WebhookProvisioningStatus.NOT_CONFIGURED,
    )
    webhook_last_error = Column(Text, nullable=True)
    webhook_last_synced_at = Column(DateTime(timezone=True), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
