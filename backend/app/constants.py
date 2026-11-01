"""Shared enumerations and constants.

Single source of truth used by the ORM check constraints, the pydantic schemas,
the rule engines, the data generator and the validation module.
This module must stay free of third-party imports so it can be imported anywhere.
"""

from typing import Dict, Iterable, Tuple

# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #
CLASSIFIABLE_CATEGORIES: Tuple[str, ...] = ("PAYROLL", "LEAVE", "BENEFITS", "ONBOARDING")
CATEGORY_CODES: Tuple[str, ...] = CLASSIFIABLE_CATEGORIES + ("IT", "GENERAL")

# --------------------------------------------------------------------------- #
# Ticket
# --------------------------------------------------------------------------- #
PRIORITIES: Tuple[str, ...] = ("P1", "P2", "P3")

TICKET_STATUSES: Tuple[str, ...] = (
    "NEW",
    "CLASSIFIED",
    "AWAITING_CLARIFICATION",
    "ASSIGNED",
    "IN_PROGRESS",
    "ESCALATED",
    "RESOLVED",
    "CLOSED",
    "REOPENED",
    "CANCELLED",
)
OPEN_STATUSES: Tuple[str, ...] = (
    "NEW",
    "CLASSIFIED",
    "AWAITING_CLARIFICATION",
    "ASSIGNED",
    "IN_PROGRESS",
    "ESCALATED",
    "REOPENED",
)
TERMINAL_STATUSES: Tuple[str, ...] = ("CLOSED", "CANCELLED")

# Valid lifecycle transitions (BUSINESS_RULES section 9). CLOSED and CANCELLED are terminal.
ALLOWED_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "NEW": ("CLASSIFIED", "ESCALATED", "CANCELLED"),
    "CLASSIFIED": ("AWAITING_CLARIFICATION", "ASSIGNED", "ESCALATED", "CANCELLED"),
    "AWAITING_CLARIFICATION": ("ASSIGNED", "ESCALATED", "CANCELLED"),
    "ASSIGNED": ("IN_PROGRESS", "ESCALATED", "CANCELLED"),
    "IN_PROGRESS": ("RESOLVED", "ESCALATED", "CANCELLED"),
    "ESCALATED": ("IN_PROGRESS", "CANCELLED"),
    "RESOLVED": ("CLOSED", "REOPENED", "CANCELLED"),
    "REOPENED": ("IN_PROGRESS", "ESCALATED", "CANCELLED"),
    "CLOSED": (),
    "CANCELLED": (),
}

TICKET_CHANNELS: Tuple[str, ...] = ("PORTAL", "EMAIL", "PHONE", "CHAT")
ACCESS_LEVELS: Tuple[str, ...] = ("STANDARD", "RESTRICTED")

TICKET_EVENT_TYPES: Tuple[str, ...] = (
    "CREATED",
    "CLASSIFIED",
    "STATUS_CHANGED",
    "ASSIGNED",
    "CLARIFICATION_REQUESTED",
    "CLARIFICATION_RECEIVED",
    "ESCALATED",
    "RESOLVED",
    "CLOSED",
    "REOPENED",
    "CANCELLED",
    "MESSAGE_ADDED",
    "PRIORITY_CHANGED",
    "SLA_PAUSED",
    "SLA_RESUMED",
    "SLA_BREACHED",
)

MESSAGE_SENDER_TYPES: Tuple[str, ...] = ("EMPLOYEE", "AGENT", "SYSTEM")
MESSAGE_TYPES: Tuple[str, ...] = (
    "PUBLIC",
    "INTERNAL_NOTE",
    "CLARIFICATION_REQUEST",
    "CLARIFICATION_RESPONSE",
    "SYSTEM",
)

ASSIGNMENT_TYPES: Tuple[str, ...] = ("AUTO", "MANUAL", "ESCALATION", "REASSIGNMENT")
ESCALATION_LEVELS: Tuple[str, ...] = ("L2", "L3")
ESCALATION_REASONS: Tuple[str, ...] = ("SENSITIVE_CASE", "SLA_BREACH", "MANUAL", "REOPEN_LIMIT")
ESCALATION_STATUSES: Tuple[str, ...] = ("OPEN", "ACKNOWLEDGED", "RESOLVED")

RESOLUTION_TYPES: Tuple[str, ...] = (
    "POLICY_ANSWER",
    "ACTION_COMPLETED",
    "REFERRED",
    "NO_ACTION_REQUIRED",
    "DUPLICATE",
)

# --------------------------------------------------------------------------- #
# Organisation / identity
# --------------------------------------------------------------------------- #
ROLE_NAMES: Tuple[str, ...] = ("EMPLOYEE", "MANAGER", "HR_PARTNER", "IT_OPS", "ADMIN")
TEAM_TYPES: Tuple[str, ...] = (
    "HR_GENERAL",
    "PAYROLL",
    "LEAVE",
    "BENEFITS",
    "ONBOARDING",
    "EMPLOYEE_RELATIONS",
    "IT_OPS",
)
SUPPORT_LEVELS: Tuple[str, ...] = ("L1", "L2")
EMPLOYMENT_TYPES: Tuple[str, ...] = ("FULL_TIME", "PART_TIME", "CONTRACTOR", "INTERN")
EMPLOYMENT_STATUSES: Tuple[str, ...] = ("ACTIVE", "ON_LEAVE", "TERMINATED")

# --------------------------------------------------------------------------- #
# Policy / knowledge
# --------------------------------------------------------------------------- #
POLICY_STATUSES: Tuple[str, ...] = ("ACTIVE", "RETIRED")
VERSION_STATUSES: Tuple[str, ...] = ("DRAFT", "PUBLISHED", "ARCHIVED")
AUDIENCE_TYPES: Tuple[str, ...] = ("ALL", "DEPARTMENT", "EMPLOYMENT_TYPE", "LOCATION")
ARTICLE_STATUSES: Tuple[str, ...] = ("DRAFT", "PUBLISHED", "ARCHIVED")

# --------------------------------------------------------------------------- #
# SLA
# --------------------------------------------------------------------------- #
SLA_POLICIES: Tuple[str, ...] = (
    "PAYROLL",
    "LEAVE",
    "BENEFITS",
    "ONBOARDING",
    "SENSITIVE",
    "GENERAL",
)
SLA_STATUSES: Tuple[str, ...] = ("ACTIVE", "PAUSED", "MET", "BREACHED")
SLA_PAUSE_REASONS: Tuple[str, ...] = ("AWAITING_CLARIFICATION", "PENDING_EMPLOYEE", "MANUAL")

# --------------------------------------------------------------------------- #
# Audit / rules
# --------------------------------------------------------------------------- #
AUDIT_ACTIONS: Tuple[str, ...] = (
    "CREATE",
    "READ",
    "UPDATE",
    "DELETE",
    "TRANSITION",
    "LOGIN",
    "LOGOUT",
    "ACCESS_DENIED",
)
RULE_TYPES: Tuple[str, ...] = ("KEYWORD", "PHRASE", "SYNONYM")

# --------------------------------------------------------------------------- #
# Misc
# --------------------------------------------------------------------------- #
SENSITIVE_QUEUE = "EMPLOYEE_RELATIONS"
DEFAULT_CALENDAR_ID = "CAL-01"


def sql_in(column: str, values: Iterable[str]) -> str:
    """Build a portable ``column IN ('A','B')`` expression for CHECK constraints."""
    quoted = ", ".join("'%s'" % v for v in values)
    return "%s IN (%s)" % (column, quoted)
