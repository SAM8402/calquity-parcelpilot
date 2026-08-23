from app.auth.models import User, UserRole


def get_data_filter(user: User) -> dict:
    if user.role == UserRole.CUSTOMER:
        return {"account_id": user.account_id}
    elif user.role in (UserRole.SUPPORT_AGENT, UserRole.OPERATIONS):
        return {}
    return {"account_id": "__NONE__"}


def can_take_actions(user: User) -> bool:
    return user.role in [UserRole.SUPPORT_AGENT, UserRole.OPERATIONS]


def get_document_filter(user: User) -> dict:
    if user.role == UserRole.CUSTOMER:
        return {
            "allowed_doc_types": ["policy", "sop", "operations_guide"],
            "customer_account_id": user.account_id,
        }
    return {}


def verify_user_access(user: User, target_account_id: str) -> bool:
    if user.role in (UserRole.SUPPORT_AGENT, UserRole.OPERATIONS):
        return True
    return user.account_id == target_account_id
