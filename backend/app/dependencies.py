"""FastAPI dependency injection: DB session, current user, role / permission checks."""

from typing import Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import AuthenticationError, ForbiddenError
from app.models.user import UserAccount
from app.security.auth import decode_token, oauth2_scheme
from app.security.permissions import has_permission

__all__ = [
    "get_db",
    "get_current_user",
    "require_permission",
    "require_any_permission",
    "require_roles",
]


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserAccount:
    """Resolve the bearer token to an active, non-deleted user."""
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Token has no subject")
    user = (
        db.query(UserAccount)
        .filter(UserAccount.user_id == user_id, UserAccount.is_deleted.is_(False))
        .first()
    )
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    return user


def require_permission(permission: str) -> Callable[..., UserAccount]:
    """Dependency factory: the user must hold ``permission`` through at least one role."""

    def checker(user: UserAccount = Depends(get_current_user)) -> UserAccount:
        if not has_permission(user.role_names, permission):
            raise ForbiddenError("Missing permission: %s" % permission)
        return user

    return checker


def require_any_permission(*permissions: str) -> Callable[..., UserAccount]:
    """Dependency factory: the user must hold at least one of ``permissions``."""

    def checker(user: UserAccount = Depends(get_current_user)) -> UserAccount:
        if not any(has_permission(user.role_names, p) for p in permissions):
            raise ForbiddenError("Requires one of: %s" % ", ".join(permissions))
        return user

    return checker


def require_roles(*roles: str) -> Callable[..., UserAccount]:
    """Dependency factory: the user must have one of the named roles."""

    def checker(user: UserAccount = Depends(get_current_user)) -> UserAccount:
        if not set(roles).intersection(user.role_names):
            raise ForbiddenError("Requires role: %s" % " or ".join(roles))
        return user

    return checker
