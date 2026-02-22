"""
Multi-tenant helpers for Telegram bot.
Provides tenant resolution and context management.
"""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import tenant_id_context
from app.core.security import get_token_hash, encrypt_token
from app.core.config import settings
from app.models.models import Tenant, TariffPlan


async def get_or_create_tenant(db: AsyncSession) -> Tenant:
    """
    Get or create tenant based on bot token.
    Uses RLS (Row Level Security) for multi-tenant isolation.
    """
    token_hash = get_token_hash(settings.TELEGRAM_BOT_TOKEN)
    
    # RLS allows this query because current_tenant_id is NULL initially
    stmt = select(Tenant).where(Tenant.bot_token_hash == token_hash)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        # Get default free tariff
        tariff_stmt = select(TariffPlan).where(TariffPlan.name == 'free')
        tariff_result = await db.execute(tariff_stmt)
        free_tariff = tariff_result.scalar_one_or_none()
        
        tenant = Tenant(
            name="Default Service", 
            encrypted_bot_token=encrypt_token(settings.TELEGRAM_BOT_TOKEN),
            bot_token_hash=token_hash,
            tariff_plan_id=free_tariff.id if free_tariff else None
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
    
    # Set context for RLS
    tenant_id_context.set(tenant.id)
    
    # We use SET LOCAL within a transaction for multi-tenant isolation.
    # This prevents the tenant_id from leaking if the connection is reused in the pool.
    if not db.in_transaction():
        await db.begin()
        
    await db.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant.id}'"))
    return tenant


async def get_tenant_shop(db: AsyncSession, tenant: Tenant):
    """
    Get the first shop for a tenant.
    Used for MVP where each tenant has one shop.
    """
    from app.models.models import Shop
    
    stmt = select(Shop).where(Shop.tenant_id == tenant.id).limit(1)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
