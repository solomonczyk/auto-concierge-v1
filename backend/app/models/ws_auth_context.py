from pydantic import BaseModel
from typing import Literal, Optional


class WSAuthContext(BaseModel):
    auth_type: Literal["ws_ticket", "cookie"] = "cookie"
    user_id: int
    tenant_id: int
    role: str
    jti: Optional[str] = None  # Only for ws_ticket; cookie auth uses session

    model_config = {"frozen": True}
