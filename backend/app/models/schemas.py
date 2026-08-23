from pydantic import BaseModel
from typing import Optional, List


class ChatRequest(BaseModel):
    message: str
    session_id: str
    user_id: str


class ChatResponse(BaseModel):
    response: str
    tools_used: List[dict]
    requires_confirmation: bool = False
    pending_action_id: Optional[str] = None
    from_cache: bool = False


class ConfirmRequest(BaseModel):
    action_id: str
    session_id: str
    user_id: str


class UserResponse(BaseModel):
    id: str
    name: str
    role: str
