from pydantic import BaseModel
from typing import Optional, List


class ToolUsage(BaseModel):
    tool: str
    input: str
    output: str


class ProactiveIssue(BaseModel):
    category: str
    count: int
    affected_accounts: Optional[int] = None
    severity: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
