from pydantic import BaseModel
from enum import Enum
from typing import Optional


class UserRole(str, Enum):
    CUSTOMER = "customer"
    SUPPORT_AGENT = "support_agent"
    OPERATIONS = "operations"


class User(BaseModel):
    user_id: str
    name: str
    role: UserRole
    account_id: Optional[str] = None


MOCK_USERS = {
    "northstar_user": User(
        user_id="northstar_user",
        name="Alex (Northstar Logistics)",
        role=UserRole.CUSTOMER,
        account_id="ACCT-001",
    ),
    "lumenworks_user": User(
        user_id="lumenworks_user",
        name="Jordan (LumenWorks)",
        role=UserRole.CUSTOMER,
        account_id="ACCT-002",
    ),
    "support_agent": User(
        user_id="support_agent",
        name="Sam (ParcelPilot Support)",
        role=UserRole.SUPPORT_AGENT,
        account_id=None,
    ),
    "ops_manager": User(
        user_id="ops_manager",
        name="Taylor (ParcelPilot Ops)",
        role=UserRole.OPERATIONS,
        account_id=None,
    ),
}
