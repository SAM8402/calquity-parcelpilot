from app.auth.models import User, UserRole


def can_take_actions(user: User) -> bool:
    return user.role in (UserRole.SUPPORT_AGENT, UserRole.OPERATIONS)


def verify_user_access(user: User, target_account_id: str) -> bool:
    if user.role in (UserRole.SUPPORT_AGENT, UserRole.OPERATIONS):
        return True
    return user.account_id == target_account_id
