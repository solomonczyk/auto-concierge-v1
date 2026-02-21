from contextvars import ContextVar
from typing import Optional

# Context variable to hold the current tenant ID
tenant_id_context: ContextVar[Optional[int]] = ContextVar("tenant_id_context", default=None)
