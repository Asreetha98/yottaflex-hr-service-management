"""Deterministic identifier builders and the regex each primary key must satisfy."""

import re
from typing import Dict


def ticket_id(n: int) -> str:
    return "TKT-2026-%06d" % n


def policy_id(n: int) -> str:
    return "POL-HR-2026-%03d" % n


def version_id(policy: str, n: int) -> str:
    return "VER-%s-%02d" % (policy, n)


def kb_id(n: int) -> str:
    return "KB-%06d" % n


def message_id(ticket: str, n: int) -> str:
    return "MSG-%s-%03d" % (ticket, n)


def user_id(n: int) -> str:
    return "USR-%06d" % n


def employee_id(n: int) -> str:
    return "EMP-%06d" % n


def department_id(n: int) -> str:
    return "DEPT-%02d" % n


def team_id(n: int) -> str:
    return "TEAM-%02d" % n


def sla_id(ticket: str) -> str:
    return "SLA-%s" % ticket


def resolution_id(ticket: str, n: int) -> str:
    return "RES-%s-%02d" % (ticket, n)


def audit_id(n: int) -> str:
    return "EVT-%06d" % n


def prefixed(prefix: str, n: int, width: int = 6) -> str:
    return "%s-%0*d" % (prefix, width, n)


# table -> regex for its primary key (single-column PKs only)
ID_PATTERNS: Dict[str, "re.Pattern[str]"] = {
    "user_accounts": re.compile(r"^USR-\d{6}$"),
    "roles": re.compile(r"^ROLE-[A-Z_]+$"),
    "permissions": re.compile(r"^PERM-[A-Z_]+$"),
    "departments": re.compile(r"^DEPT-\d{2}$"),
    "teams": re.compile(r"^TEAM-\d{2}$"),
    "employees": re.compile(r"^EMP-\d{6}$"),
    "policy_documents": re.compile(r"^POL-HR-2026-\d{3}$"),
    "policy_versions": re.compile(r"^VER-POL-HR-2026-\d{3}-\d{2}$"),
    "policy_audiences": re.compile(r"^AUD-\d{6}$"),
    "policy_citations": re.compile(r"^CIT-\d{6}$"),
    "categories": re.compile(r"^CAT-\d{2}$"),
    "knowledge_articles": re.compile(r"^KB-\d{6}$"),
    "tickets": re.compile(r"^TKT-2026-\d{6}$"),
    "messages": re.compile(r"^MSG-TKT-2026-\d{6}-\d{3}$"),
    "ticket_events": re.compile(r"^TEV-\d{6}$"),
    "assignments": re.compile(r"^ASG-\d{6}$"),
    "escalations": re.compile(r"^ESC-\d{6}$"),
    "business_calendars": re.compile(r"^CAL-\d{2}$"),
    "holiday_calendars": re.compile(r"^HOL-\d{6}$"),
    "slas": re.compile(r"^SLA-TKT-2026-\d{6}$"),
    "sla_pause_events": re.compile(r"^PAU-\d{6}$"),
    "resolutions": re.compile(r"^RES-TKT-2026-\d{6}-\d{2}$"),
    "audit_logs": re.compile(r"^EVT-\d{6}$"),
    "category_rules": re.compile(r"^CRL-\d{6}$"),
    "routing_rules": re.compile(r"^RRL-\d{2}$"),
    "clarification_templates": re.compile(r"^CLT-\d{2}$"),
}
