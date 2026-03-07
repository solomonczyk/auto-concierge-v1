from pydantic import BaseModel
from typing import Literal


class WSAuthContext(BaseModel):
    auth_type: Literal["ws_ticket"] = "ws_ticket"
    user_id: int
    tenant_id: int
    role: str
    jti: str

    model_config = {"frozen": True}
