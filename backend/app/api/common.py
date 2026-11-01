"""Small shared helpers for route modules."""

from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.user import UserAccount
from app.exceptions import BusinessRuleError
from app.schemas.auth import UserOut
from app.security.permissions import permissions_for_roles


def client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def user_out(user: UserAccount) -> UserOut:
    return UserOut(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        employee_id=user.employee_id,
        is_active=user.is_active,
        can_view_sensitive=user.can_view_sensitive,
        roles=sorted(user.role_names),
        permissions=sorted(permissions_for_roles(user.role_names)),
        last_login_at=user.last_login_at,
    )


def require_employee(db: Session, user: UserAccount) -> Employee:
    """The caller's employee record (needed to raise tickets)."""
    employee = (
        db.query(Employee)
        .filter(Employee.employee_id == user.employee_id, Employee.is_deleted.is_(False))
        .first()
        if user.employee_id
        else None
    )
    if employee is None:
        raise BusinessRuleError("This account is not linked to an employee record", "NO_EMPLOYEE")
    return employee
