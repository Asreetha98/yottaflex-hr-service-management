"""Role-permission matrix and permission-checking helpers."""

from functools import wraps
from typing import Any, Callable, Dict, FrozenSet, Iterable, Optional

from app.exceptions import ForbiddenError

EMPLOYEE_PERMISSIONS: FrozenSet[str] = frozenset(
    {"submit_ticket", "view_own_tickets", "send_message", "view_knowledge"}
)
MANAGER_PERMISSIONS: FrozenSet[str] = EMPLOYEE_PERMISSIONS | {
    "view_team_tickets", "escalate_ticket", "approve_requests",
}
HR_PARTNER_PERMISSIONS: FrozenSet[str] = MANAGER_PERMISSIONS | {
    "manage_tickets", "view_all_tickets", "resolve_tickets", "view_sensitive_tickets",
    "manage_knowledge", "view_analytics",
}
IT_OPS_PERMISSIONS: FrozenSet[str] = frozenset(
    {"send_message", "view_knowledge", "manage_tickets", "view_all_tickets", "resolve_tickets"}
)
ADMIN_PERMISSIONS: FrozenSet[str] = HR_PARTNER_PERMISSIONS | {
    "manage_users", "manage_roles", "manage_policies", "manage_config", "view_audit_logs",
    "manage_sensitive_tickets",
}

ROLE_PERMISSIONS: Dict[str, FrozenSet[str]] = {
    "EMPLOYEE": EMPLOYEE_PERMISSIONS,
    "MANAGER": MANAGER_PERMISSIONS,
    "HR_PARTNER": HR_PARTNER_PERMISSIONS,
    "IT_OPS": IT_OPS_PERMISSIONS,
    "ADMIN": ADMIN_PERMISSIONS,
}

ALL_PERMISSIONS: FrozenSet[str] = frozenset().union(*ROLE_PERMISSIONS.values())

PERMISSION_DESCRIPTIONS: Dict[str, str] = {
    "submit_ticket": "Create HR tickets",
    "view_own_tickets": "View tickets the user raised",
    "send_message": "Add messages to accessible tickets",
    "view_knowledge": "Search and read knowledge articles",
    "view_team_tickets": "View tickets raised by direct reports",
    "escalate_ticket": "Escalate a ticket to L2",
    "approve_requests": "Approve employee requests",
    "manage_tickets": "Assign and work tickets",
    "view_all_tickets": "View every non-restricted ticket",
    "resolve_tickets": "Resolve and close tickets",
    "view_sensitive_tickets": "View restricted tickets (requires explicit authorisation flag)",
    "manage_knowledge": "Create and publish knowledge articles",
    "view_analytics": "View analytics dashboards",
    "manage_users": "Create and edit users",
    "manage_roles": "Assign roles",
    "manage_policies": "Create, publish and archive policies",
    "manage_config": "Edit rules and calendars",
    "view_audit_logs": "Read the audit log",
    "manage_sensitive_tickets": "Full access to restricted tickets",
}

# IT_OPS may only act on tickets of this category code.
IT_OPS_CATEGORY = "IT"


def permissions_for_roles(role_names: Iterable[str]) -> FrozenSet[str]:
    granted: FrozenSet[str] = frozenset()
    for role in role_names:
        granted |= ROLE_PERMISSIONS.get(role, frozenset())
    return granted


def has_permission(role_names: Iterable[str], permission: str) -> bool:
    return permission in permissions_for_roles(role_names)


def is_admin(role_names: Iterable[str]) -> bool:
    return "ADMIN" in set(role_names)


def can_manage_category(role_names: Iterable[str], category_code: Optional[str]) -> bool:
    """HR_PARTNER / ADMIN manage every category; IT_OPS only the IT category."""
    roles = set(role_names)
    if roles & {"ADMIN", "HR_PARTNER"}:
        return True
    return "IT_OPS" in roles and category_code == IT_OPS_CATEGORY


def can_view_sensitive(role_names: Iterable[str], has_authorization_flag: bool) -> bool:
    """ADMIN always; HR_PARTNER only with the explicit ``can_view_sensitive`` flag."""
    roles = set(role_names)
    if "ADMIN" in roles:
        return True
    return "HR_PARTNER" in roles and has_authorization_flag


def permission_required(permission: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for service functions that receive ``user`` (a ``UserAccount``) as a keyword.

    FastAPI routes should use ``dependencies.require_permission`` instead.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user = kwargs.get("user") or kwargs.get("actor")
            if user is None or not has_permission(user.role_names, permission):
                raise ForbiddenError("Missing permission: %s" % permission)
            return func(*args, **kwargs)

        return wrapper

    return decorator
