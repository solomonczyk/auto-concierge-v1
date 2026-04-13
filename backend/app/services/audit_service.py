"""
Universal audit log service. Minimal scope: appointments, clients, auth.
Does not replace AppointmentHistory (status changes).
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AuditLog

logger = logging.getLogger(__name__)


def _safe_payload(obj: Any) -> Optional[dict]:
    """Build a minimal JSON-serializable payload, excluding secrets."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        out = {}
        skip = {"hashed_password", "password", "encrypted_bot_token", "bot_token_hash", "secret"}
        for k, v in obj.items():
            if k.lower() in skip:
                continue
            try:
                if isinstance(v, (str, int, float, bool, type(None))):
                    out[k] = v
                elif hasattr(v, "isoformat"):
                    out[k] = v.isoformat()
                else:
                    out[k] = str(v)[:200]
            except Exception:
                out[k] = "<non-serializable>"
        return out
    return {"_repr": str(obj)[:500]}


async def log_audit(
    db: AsyncSession,
    *,
    tenant_id: Optional[int],
    actor_user_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    payload_before: Optional[dict] = None,
    payload_after: Optional[dict] = None,
    source: str = "api",
) -> None:
    """
    Write a single audit log entry. Never raises — failures are logged only.
    Uses a savepoint so a failed flush cannot poison the outer transaction
    (e.g. login commit after a bad audit insert).
    """
    try:
        async with db.begin_nested():
            entry = AuditLog(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id is not None else None,
                payload_before=_safe_payload(payload_before),
                payload_after=_safe_payload(payload_after),
                source=source,
            )
            db.add(entry)
            await db.flush()
    except Exception as exc:
        logger.warning(
            "audit_log.write_failed action=%s entity_type=%s entity_id=%s: %s",
            action,
            entity_type,
            entity_id,
            exc,
        )
