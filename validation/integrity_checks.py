"""Structural integrity checks on the generated CSV files (keys, references, enums, time ordering)."""

import csv
import os
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

import generator  # noqa: F401  (puts backend/ on sys.path)
from generator.utils.dataset import COLUMNS
from app import constants as K

PRIMARY_KEYS = {
    "roles": "role_id", "permissions": "permission_id", "departments": "department_id", "teams": "team_id",
    "employees": "employee_id", "user_accounts": "user_id", "categories": "category_id",
    "category_rules": "rule_id", "routing_rules": "rule_id", "clarification_templates": "template_id",
    "business_calendars": "calendar_id", "holiday_calendars": "holiday_id", "policy_documents": "policy_id",
    "policy_versions": "version_id", "policy_audiences": "audience_id", "knowledge_articles": "article_id",
    "policy_citations": "citation_id", "tickets": "ticket_id", "messages": "message_id",
    "ticket_events": "event_id", "assignments": "assignment_id", "escalations": "escalation_id", "slas": "sla_id",
    "sla_pause_events": "pause_id", "resolutions": "resolution_id", "audit_logs": "event_id",
}
FOREIGN_KEYS = (
    ("teams", "department_id", "departments", "department_id"),
    ("employees", "department_id", "departments", "department_id"),
    ("employees", "manager_id", "employees", "employee_id"),
    ("user_accounts", "employee_id", "employees", "employee_id"),
    ("user_roles", "user_id", "user_accounts", "user_id"),
    ("user_roles", "role_id", "roles", "role_id"),
    ("policy_versions", "policy_id", "policy_documents", "policy_id"),
    ("policy_audiences", "version_id", "policy_versions", "version_id"),
    ("policy_citations", "version_id", "policy_versions", "version_id"),
    ("knowledge_articles", "policy_version_id", "policy_versions", "version_id"),
    ("tickets", "requester_id", "employees", "employee_id"),
    ("tickets", "category_id", "categories", "category_id"),
    ("tickets", "assigned_team_id", "teams", "team_id"),
    ("messages", "ticket_id", "tickets", "ticket_id"),
    ("ticket_events", "ticket_id", "tickets", "ticket_id"),
    ("assignments", "ticket_id", "tickets", "ticket_id"),
    ("assignments", "team_id", "teams", "team_id"),
    ("escalations", "ticket_id", "tickets", "ticket_id"),
    ("slas", "ticket_id", "tickets", "ticket_id"),
    ("sla_pause_events", "sla_id", "slas", "sla_id"),
    ("resolutions", "ticket_id", "tickets", "ticket_id"),
    ("resolutions", "policy_version_id", "policy_versions", "version_id"),
    ("resolutions", "citation_id", "policy_citations", "citation_id"),
    ("resolutions", "article_id", "knowledge_articles", "article_id"),
    ("resolutions", "resolved_by", "user_accounts", "user_id"),
)
ENUMS = (
    ("tickets", "status", K.TICKET_STATUSES), ("tickets", "priority", K.PRIORITIES),
    ("tickets", "channel", K.TICKET_CHANNELS), ("ticket_events", "event_type", K.TICKET_EVENT_TYPES),
    ("audit_logs", "action", K.AUDIT_ACTIONS), ("slas", "status", K.SLA_STATUSES),
    ("resolutions", "resolution_type", K.RESOLUTION_TYPES), ("escalations", "status", K.ESCALATION_STATUSES),
    ("policy_versions", "status", K.VERSION_STATUSES), ("policy_documents", "status", K.POLICY_STATUSES),
    ("messages", "sender_type", K.MESSAGE_SENDER_TYPES), ("messages", "message_type", K.MESSAGE_TYPES),
)
ORDERING = (
    ("tickets", "created_at", "resolved_at"), ("tickets", "resolved_at", "closed_at"),
    ("assignments", "assigned_at", "unassigned_at"), ("slas", "started_at", "due_at"),
    ("sla_pause_events", "paused_at", "resumed_at"), ("policy_versions", "effective_from", "effective_to"),
)


def load_tables(directory: str) -> Dict[str, List[Dict[str, str]]]:
    tables: Dict[str, List[Dict[str, str]]] = {}
    for table in COLUMNS:
        path = os.path.join(directory, "%s.csv" % table)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", newline="") as handle:
                tables[table] = list(csv.DictReader(handle))
    return tables


def parse(value: str) -> Any:
    return datetime.fromisoformat(value) if value else None


def finding(check: str, severity: str, entity_type: str, entity_id: str, message: str,
            anomaly_type: Any = None, ticket_id: Any = None) -> Dict[str, Any]:
    return {"check": check, "severity": severity, "entity_type": entity_type, "entity_id": entity_id,
            "ticket_id": ticket_id, "anomaly_type": anomaly_type, "message": message}


def run_integrity_checks(tables: Dict[str, List[Dict[str, str]]], expected: Dict[str, int]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for table in COLUMNS:
        if table not in tables:
            out.append(finding("table_present", "CRITICAL", table, table, "CSV file is missing"))
    for table, want in expected.items():
        got = len(tables.get(table, []))
        if got != want:
            out.append(finding("row_count", "CRITICAL", table, table, "expected %d rows, found %d" % (want, got)))
    for table, key in PRIMARY_KEYS.items():
        counts = Counter(r[key] for r in tables.get(table, []))
        for value, n in counts.items():
            if n > 1 or not value:
                out.append(finding("primary_key_unique", "CRITICAL", table, value, "duplicate or empty key"))
    for table, col, ref_table, ref_col in FOREIGN_KEYS:
        valid = {r[ref_col] for r in tables.get(ref_table, [])}
        for r in tables.get(table, []):
            if r[col] and r[col] not in valid:
                out.append(finding("foreign_key", "CRITICAL", table, r[PRIMARY_KEYS.get(table, col)],
                                   "%s=%s not found in %s" % (col, r[col], ref_table)))
    for table, col, allowed in ENUMS:
        for r in tables.get(table, []):
            if r[col] not in allowed:
                out.append(finding("enum_value", "CRITICAL", table, r.get(PRIMARY_KEYS.get(table, col), ""),
                                   "%s=%s not allowed" % (col, r[col])))
    for table, early, late in ORDERING:
        for r in tables.get(table, []):
            if r[early] and r[late] and r[late] < r[early]:
                out.append(finding("time_ordering", "CRITICAL", table, r[PRIMARY_KEYS.get(table, early)],
                                   "%s is before %s" % (late, early)))
    seq: Dict[str, List[int]] = {}
    for m in tables.get("messages", []):
        seq.setdefault(m["ticket_id"], []).append(int(m["sequence_number"]))
    for tid, nums in seq.items():
        if sorted(nums) != list(range(1, len(nums) + 1)):
            out.append(finding("message_sequence", "CRITICAL", "messages", tid, "sequence numbers not contiguous"))
    ref = max((r["created_at"] for r in tables.get("messages", [])), default="")
    if ref > "2026-10-22T17:00:00+00:00":
        out.append(finding("no_future_data", "CRITICAL", "messages", "-", "message after reference date"))
    return out
