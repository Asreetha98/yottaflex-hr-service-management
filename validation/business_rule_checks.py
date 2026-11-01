"""Business-rule checks. Each finding is later matched against the anomaly register."""

from datetime import date
from typing import Any, Dict, List

import generator  # noqa: F401
from app.constants import ALLOWED_TRANSITIONS
from generator.config import REFERENCE_DATE
from generator.utils.calendar_util import CALC
from validation.integrity_checks import finding, parse

VERIFIED_WORDS = ("verified", "confirmed per", "policy-verified")


def _in_force(version: Dict[str, str], day: date) -> bool:
    """Effective window check; superseded (ARCHIVED) versions were in force within their own window."""
    if version["status"] == "DRAFT":
        return False
    start = date.fromisoformat(version["effective_from"]) if version["effective_from"] else None
    end = date.fromisoformat(version["effective_to"]) if version["effective_to"] else None
    return (start is None or start <= day) and (end is None or day <= end)


def run_business_checks(t: Dict[str, List[Dict[str, str]]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    tickets = {r["ticket_id"]: r for r in t["tickets"]}
    versions = {r["version_id"]: r for r in t["policy_versions"]}
    policies = {r["policy_id"]: r for r in t["policy_documents"]}
    teams = {r["team_id"]: r for r in t["teams"]}

    # 1. lifecycle transitions
    for e in t["ticket_events"]:
        if e["from_status"] and e["to_status"] and e["from_status"] != e["to_status"]:
            if e["to_status"] not in ALLOWED_TRANSITIONS.get(e["from_status"], ()):
                out.append(finding("lifecycle_transition", "HIGH", "ticket_events", e["ticket_id"],
                                   "illegal transition %s -> %s" % (e["from_status"], e["to_status"]),
                                   "INVALID_LIFECYCLE_TRANSITION", e["ticket_id"]))

    # 2. sensitive tickets must sit in a restricted team
    for a in t["assignments"]:
        tk = tickets[a["ticket_id"]]
        if a["is_current"] == "true" and tk["is_sensitive"] == "true" and not (teams[a["team_id"]]["is_restricted"] == "true"):
            out.append(finding("sensitive_routing", "CRITICAL", "assignments", a["assignment_id"],
                               "sensitive ticket in unrestricted team %s" % a["team_id"],
                               "SENSITIVE_IN_GENERAL_QUEUE", a["ticket_id"]))

    # 3. SLA deadline must equal business-hour arithmetic (plus paused business minutes)
    for s in t["slas"]:
        started, due = parse(s["started_at"]), parse(s["due_at"])
        want = int(float(s["target_hours"]) * 60) + int(s["total_paused_business_minutes"] or 0)
        got = CALC.elapsed_business_minutes(started, due)
        if abs(got - want) > 1:
            out.append(finding("sla_business_hours", "HIGH", "slas", s["sla_id"],
                               "due_at spans %d business minutes, expected %d" % (got, want),
                               "SLA_EXCLUDES_BUSINESS_HOURS", s["ticket_id"]))
        if (s["is_breached"] == "true") != (s["status"] == "BREACHED") and s["status"] in ("BREACHED", "MET"):
            out.append(finding("sla_status_consistent", "HIGH", "slas", s["sla_id"], "status and is_breached disagree",
                               None, s["ticket_id"]))
        tk = tickets[s["ticket_id"]]
        if s["status"] == "BREACHED" and tk["status"] not in ("CLOSED", "RESOLVED", "CANCELLED"):
            out.append(finding("open_sla_breach", "MEDIUM", "slas", s["sla_id"], "open ticket past its deadline",
                               "SLA_BREACH", s["ticket_id"]))

    # 4. resolutions: policy version validity and sources
    for r in t["resolutions"]:
        tk = tickets[r["ticket_id"]]
        text = r["resolution_text"].lower()
        if r["resolution_type"] == "POLICY_ANSWER" and not r["policy_version_id"]:
            if any(w in text for w in VERIFIED_WORDS):
                out.append(finding("unsupported_claim", "CRITICAL", "resolutions", r["resolution_id"],
                                   "claim presented as verified without a source", "UNSUPPORTED_CLAIM_AS_VERIFIED",
                                   r["ticket_id"]))
            else:
                out.append(finding("policy_source_present", "HIGH", "resolutions", r["resolution_id"],
                                   "policy answer has no source", "MISSING_POLICY_SOURCE", r["ticket_id"]))
            continue
        if r["policy_version_id"]:
            v = versions[r["policy_version_id"]]
            if policies[v["policy_id"]]["status"] == "RETIRED":
                out.append(finding("policy_not_expired", "HIGH", "resolutions", r["resolution_id"],
                                   "cites retired policy %s" % v["policy_id"], "EXPIRED_POLICY_REFERENCE", r["ticket_id"]))
            elif not _in_force(v, parse(tk["created_at"]).date()):
                out.append(finding("policy_version_current", "HIGH", "resolutions", r["resolution_id"],
                                   "cites %s which was not in force on the ticket date" % v["version_id"],
                                   "OBSOLETE_POLICY_CITATION", r["ticket_id"]))

    # 5. only one version of a policy may be in force today
    by_policy: Dict[str, List[Dict[str, str]]] = {}
    for v in t["policy_versions"]:
        if _in_force(v, REFERENCE_DATE):
            by_policy.setdefault(v["policy_id"], []).append(v)
    for pid, vs in by_policy.items():
        if len(vs) > 1:
            oldest = min(vs, key=lambda v: int(v["version_number"]))
            out.append(finding("single_version_in_force", "HIGH", "policy_versions", oldest["version_id"],
                               "%d versions of %s are in force" % (len(vs), pid), "CONFLICTING_POLICY_MATCHES"))

    # 6. consecutive duplicate messages
    last: Dict[str, Dict[str, str]] = {}
    for m in sorted(t["messages"], key=lambda m: (m["ticket_id"], int(m["sequence_number"]))):
        p = last.get(m["ticket_id"])
        if p and p["body"] == m["body"] and p["sender_user_id"] == m["sender_user_id"] and m["sender_type"] != "SYSTEM":
            out.append(finding("duplicate_message", "LOW", "messages", m["message_id"], "repeats previous message",
                               "DUPLICATE_MESSAGE", m["ticket_id"]))
        last[m["ticket_id"]] = m

    # 7. denied access attempts
    for a in t["audit_logs"]:
        if a["action"] == "ACCESS_DENIED":
            out.append(finding("access_denied", "HIGH", "audit_logs", a["entity_id"],
                               "denied access by %s" % a["actor_user_id"], "UNAUTHORIZED_ACCESS_ATTEMPT", a["entity_id"]))

    # 8. employees whose context is incomplete
    for e in t["employees"]:
        if not e["job_title"]:
            out.append(finding("employee_context", "MEDIUM", "employees", e["employee_id"],
                               "no job title / manager / team on record", "MISSING_EMPLOYEE_CONTEXT"))

    # 9. ambiguous tickets that were closed without a clarification request
    asked = {e["ticket_id"] for e in t["ticket_events"] if e["event_type"] == "CLARIFICATION_REQUESTED"}
    for tk in t["tickets"]:
        if tk["is_ambiguous"] == "true" and tk["ticket_id"] not in asked and tk["status"] in ("CLOSED", "RESOLVED"):
            out.append(finding("ambiguity_clarified", "MEDIUM", "tickets", tk["ticket_id"],
                               "ambiguous ticket resolved without clarification", "AMBIGUOUS_CLASSIFICATION",
                               tk["ticket_id"]))
    return out
