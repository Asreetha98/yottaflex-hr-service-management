"""In-memory dataset container, column layout of every table and deterministic CSV output."""

import csv
import hashlib
import json
import os
from collections import OrderedDict
from datetime import date, datetime, time, timezone
from typing import Any, Dict, Iterable, List, Optional

from generator.config import DatasetSize, FULL_SIZE

_TS = ["created_at", "updated_at"]
_SD = ["is_deleted", "deleted_at"]

# Column order of each CSV. Mirrors documentation/DATA_DICTIONARY.md.
COLUMNS: "OrderedDict[str, List[str]]" = OrderedDict([
    ("roles", ["role_id", "name", "description"] + _TS),
    ("permissions", ["permission_id", "code", "description"] + _TS),
    ("role_permissions", ["role_id", "permission_id"]),
    ("departments", ["department_id", "code", "name", "description", "is_active"] + _TS + _SD),
    ("teams", ["team_id", "name", "department_id", "team_type", "support_level", "is_restricted", "is_active"] + _TS + _SD),
    ("employees", ["employee_id", "first_name", "last_name", "email", "department_id", "team_id", "manager_id",
                   "job_title", "employment_type", "employment_status", "location", "hire_date",
                   "termination_date"] + _TS + _SD),
    ("user_accounts", ["user_id", "employee_id", "username", "email", "password_hash", "is_active",
                       "can_view_sensitive", "last_login_at"] + _TS + _SD),
    ("user_roles", ["user_id", "role_id", "assigned_at", "assigned_by"]),
    ("categories", ["category_id", "code", "name", "description", "is_active"] + _TS + _SD),
    ("category_rules", ["rule_id", "category_id", "rule_type", "term", "weight", "is_active"] + _TS + _SD),
    ("routing_rules", ["rule_id", "name", "category_id", "is_sensitive", "priority_order", "target_team_id",
                       "description", "is_active"] + _TS + _SD),
    ("clarification_templates", ["template_id", "category_id", "required_field", "question_text",
                                 "detection_keywords", "display_order", "is_active"] + _TS + _SD),
    ("business_calendars", ["calendar_id", "name", "timezone", "work_days", "start_time", "end_time",
                            "is_default"] + _TS + _SD),
    ("holiday_calendars", ["holiday_id", "calendar_id", "holiday_date", "name"] + _TS + _SD),
    ("policy_documents", ["policy_id", "title", "description", "category_id", "owner_department_id",
                          "status"] + _TS + _SD),
    ("policy_versions", ["version_id", "policy_id", "version_number", "title", "content", "summary", "status",
                         "effective_from", "effective_to", "published_at", "published_by", "created_by",
                         "supersedes_version_id"] + _TS + _SD),
    ("policy_audiences", ["audience_id", "version_id", "audience_type", "audience_value"] + _TS),
    ("knowledge_articles", ["article_id", "title", "summary", "content", "primary_category_id",
                            "policy_version_id", "keywords", "audience", "status", "view_count", "published_at",
                            "last_reviewed_at", "author_id"] + _TS + _SD),
    ("article_categories", ["article_id", "category_id"]),
    ("policy_citations", ["citation_id", "version_id", "article_id", "section_reference", "excerpt"] + _TS),
    ("tickets", ["ticket_id", "requester_id", "subject", "description", "category_id", "priority", "status",
                 "channel", "is_sensitive", "access_level", "sensitive_patterns", "classification_confidence",
                 "classification_explanation", "is_ambiguous", "assigned_team_id", "assigned_user_id",
                 "reopen_count", "first_response_at", "resolved_at", "closed_at"] + _TS + _SD),
    ("messages", ["message_id", "ticket_id", "sequence_number", "sender_user_id", "sender_type", "message_type",
                  "is_internal", "body"] + _TS + _SD),
    ("ticket_events", ["event_id", "ticket_id", "event_type", "from_status", "to_status", "actor_user_id",
                       "details", "created_at"]),
    ("assignments", ["assignment_id", "ticket_id", "team_id", "assigned_user_id", "assigned_by", "assignment_type",
                     "routing_reason", "rule_reference", "is_current", "assigned_at", "unassigned_at",
                     "created_at"]),
    ("escalations", ["escalation_id", "ticket_id", "from_team_id", "to_team_id", "escalation_level", "reason_code",
                     "reason", "escalated_by", "escalated_at", "status", "resolved_at"] + _TS),
    ("slas", ["sla_id", "ticket_id", "calendar_id", "sla_policy", "priority", "target_hours",
              "first_response_target_hours", "started_at", "due_at", "first_response_due_at", "first_response_at",
              "resolved_at", "total_paused_business_minutes", "status", "is_breached", "breached_at"] + _TS),
    ("sla_pause_events", ["pause_id", "sla_id", "reason", "paused_at", "resumed_at", "business_minutes_paused",
                          "paused_by", "created_at"]),
    ("resolutions", ["resolution_id", "ticket_id", "resolution_type", "summary", "resolution_text",
                     "policy_version_id", "citation_id", "article_id", "resolved_by", "resolved_at",
                     "satisfaction_score", "was_reopened"] + _TS + _SD),
    ("audit_logs", ["event_id", "event_type", "action", "entity_type", "entity_id", "actor_user_id", "actor_role",
                    "old_values", "new_values", "ip_address", "created_at"]),
])

JSON_COLUMNS = {
    "sensitive_patterns", "classification_explanation", "details", "keywords", "audience", "work_days",
    "detection_keywords", "old_values", "new_values",
}


def format_value(value: Any) -> str:
    """Canonical, locale-independent text form of a cell."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.strftime("%H:%M:%S")
    if isinstance(value, float):
        return repr(round(value, 6))
    if isinstance(value, (list, dict, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return str(value)


class Dataset:
    """All generated tables, keyed by table name, rows kept as plain dicts."""

    def __init__(self, size: DatasetSize = FULL_SIZE) -> None:
        self.size = size
        self.tables: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict((t, []) for t in COLUMNS)
        self.extra: Dict[str, Any] = {}

    def add(self, table: str, **row: Any) -> Dict[str, Any]:
        unknown = set(row) - set(COLUMNS[table])
        if unknown:
            raise KeyError("Unknown column(s) %s for %s" % (sorted(unknown), table))
        full = {c: row.get(c) for c in COLUMNS[table]}
        self.tables[table].append(full)
        return full

    def rows(self, table: str) -> List[Dict[str, Any]]:
        return self.tables[table]

    def index(self, table: str, key: str) -> Dict[Any, Dict[str, Any]]:
        return {r[key]: r for r in self.tables[table]}

    def counts(self) -> Dict[str, int]:
        return {t: len(r) for t, r in self.tables.items()}


def write_csv(path: str, columns: Iterable[str], rows: Iterable[Dict[str, Any]]) -> None:
    cols = list(columns)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(cols)
        for row in rows:
            writer.writerow([format_value(row.get(c)) for c in cols])


def write_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2, ensure_ascii=False)
        handle.write("\n")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_dataset(ds: Dataset, out_dir: str) -> Dict[str, Dict[str, Any]]:
    """Write one CSV per table; returns ``{filename: {rows, sha256}}``."""
    os.makedirs(out_dir, exist_ok=True)
    manifest: Dict[str, Dict[str, Any]] = {}
    for table, columns in COLUMNS.items():
        path = os.path.join(out_dir, "%s.csv" % table)
        write_csv(path, columns, ds.tables[table])
        manifest["%s.csv" % table] = {"rows": len(ds.tables[table]), "sha256": sha256_file(path)}
    return manifest


def read_csv_rows(path: str) -> Optional[List[Dict[str, str]]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
