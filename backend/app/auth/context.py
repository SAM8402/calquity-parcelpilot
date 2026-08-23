"""Request-scoped user context for tool-layer access control."""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

from app.auth.models import User

_current_user: ContextVar[Optional[User]] = ContextVar("current_user", default=None)


def set_current_user(user: User) -> None:
    _current_user.set(user)


def get_current_user() -> Optional[User]:
    return _current_user.get()
