"""Inject the 13 labelled anomaly types into a generated dataset.

Every injection mutates the operational tables in place and appends one entry to the anomaly
register. The register is written to the ground-truth files only, never to operational tables.
"""

import random
from datetime import timedelta
from typing import Any, Callable, Dict, List, Set

from generator.config import REFERENCE_NOW, stage_rng
from generator.utils.calendar_util import CALC
from generator.utils.dataset import Dataset
from app.rules.classification_engine import ClassificationEngine

ANOMALY_TYPES = (
    "OBSOLETE_POLICY_CITATION", "SENSITIVE_IN_GENERAL_QUEUE", "SLA_EXCLUDES_BUSINESS_HOURS",
    "UNSUPPORTED_CLAIM_AS_VERIFIED", "MISSING_EMPLOYEE_CONTEXT", "AMBIGUOUS_CLASSIFICATION",
    "EXPIRED_POLICY_REFERENCE", "CONFLICTING_POLICY_MATCHES", "MISSING_POLICY_SOURCE", "DUPLICATE_MESSAGE",
    "INVALID_LIFECYCLE_TRANSITION", "SLA_BREACH", "UNAUTHORIZED_ACCESS_ATTEMPT",
)
MANDATORY = ("OBSOLETE_POLICY_CITATION", "SENSITIVE_IN_GENERAL_QUEUE", "SLA_EXCLUDES_BUSINESS_HOURS",
             "UNSUPPORTED_CLAIM_AS_VERIFIED")

_CLASSIFY = ClassificationEngine()
_AMBIGUOUS_TEXT = (
    ("Question about pay and leave", "I have a question about my salary deduction for the leave I took and my insurance "
     "enrolment. Not sure who handles this."),
    ("Leave and payroll mix-up", "My leave balance and my payslip both look wrong this month, and my benefits premium "
     "changed as well."),
    ("Need help with several things", "Need help with a bonus payment, my sick leave record and adding a dependent to "
     "my health plan."),
    ("Pay or leave issue?", "I took unpaid leave and my pay dropped, maybe the insurance deduction is also wrong. "
     "Please check everything."),
    ("General HR question", "Can someone look at my leave, my pay and my joining paperwork? Something is off."),
)


class _Ctx:
    def __init__(self, ds: Dataset) -> None:
        self.ds = ds
        self.rng: random.Random = stage_rng("anomalies")
        self.count = ds.size.anomalies_per_type
        self.used: Set[str] = set()
        self.register: List[Dict[str, Any]] = []
        self.tickets = ds.index("tickets", "ticket_id")
        self.slas = ds.index("slas", "ticket_id")
        self.versions = ds.index("policy_versions", "version_id")
        self.citations = {c["version_id"]: c["citation_id"] for c in ds.rows("policy_citations")}
        self.resolutions_by_ticket: Dict[str, List[Dict[str, Any]]] = {}
        for r in ds.rows("resolutions"):
            self.resolutions_by_ticket.setdefault(r["ticket_id"], []).append(r)
        self.next_event = len(ds.rows("ticket_events")) + 1
        self.next_audit = len(ds.rows("audit_logs")) + 1
        self.counters: Dict[str, int] = {}

    def pick(self, candidates: List[Any], key: Callable[[Any], str]) -> List[Any]:
        pool = [c for c in candidates if key(c) not in self.used]
        pool.sort(key=key)
        chosen = self.rng.sample(pool, min(self.count, len(pool)))
        chosen.sort(key=key)
        for c in chosen:
            self.used.add(key(c))
        return chosen

    def record(self, atype: str, entity_type: str, entity_id: str, ticket_id: Any, description: str,
               expected: str, condition: str, severity: str) -> None:
        self.counters[atype] = self.counters.get(atype, 0) + 1
        self.register.append({
            "issue_id": "ANOM-%s-%02d" % (atype, self.counters[atype]), "anomaly_type": atype,
            "entity_type": entity_type, "entity_id": entity_id, "ticket_id": ticket_id,
            "description": description, "expected_behaviour": expected, "injected_condition": condition,
            "severity": severity, "mandatory": atype in MANDATORY, "label": "INJECTED",
        })

    def add_event(self, ticket_id: str, etype: str, from_s: Any, to_s: Any, ts: Any, details: Any) -> None:
        self.ds.add("ticket_events", event_id="TEV-%06d" % self.next_event, ticket_id=ticket_id, event_type=etype,
                    from_status=from_s, to_status=to_s, actor_user_id=None, details=details, created_at=ts)
        self.next_event += 1

    def add_audit(self, **row: Any) -> None:
        self.ds.add("audit_logs", event_id="EVT-%06d" % self.next_audit, **row)
        self.next_audit += 1


def _policy_resolutions(c: _Ctx) -> List[Dict[str, Any]]:
    return [r for r in c.ds.rows("resolutions") if r["resolution_type"] == "POLICY_ANSWER" and r["policy_version_id"]]


def _text(version: Dict[str, Any]) -> str:
    return "As per %s (version %d): %s" % (version["title"], version["version_number"], version["summary"])


def obsolete_policy(c: _Ctx) -> None:
    cands = []
    for r in _policy_resolutions(c):
        v = c.versions[r["policy_version_id"]]
        prev = c.versions.get(v["supersedes_version_id"]) if v["supersedes_version_id"] else None
        t = c.tickets[r["ticket_id"]]
        if (prev and prev["status"] == "ARCHIVED" and prev["effective_to"] and v["effective_from"]
                and t["created_at"].date() >= v["effective_from"] and r["ticket_id"] not in c.used):
            cands.append(r)
    for r in c.pick(cands, lambda x: x["ticket_id"]):
        v = c.versions[r["policy_version_id"]]
        old = c.versions[v["supersedes_version_id"]]
        r["policy_version_id"], r["citation_id"], r["article_id"] = old["version_id"], c.citations.get(old["version_id"]), None
        r["resolution_text"] = _text(old)
        c.used.add("policy:" + old["policy_id"])
        c.record("OBSOLETE_POLICY_CITATION", "resolutions", r["resolution_id"], r["ticket_id"],
                 "Answer cites %s (v%d), superseded on %s." % (old["policy_id"], old["version_number"], v["effective_from"]),
                 "Answer must cite the version in force on the ticket date (%s)." % v["version_id"],
                 "resolution.policy_version_id replaced with archived version %s" % old["version_id"], "HIGH")


def sensitive_in_general(c: _Ctx) -> None:
    current = {a["ticket_id"]: a for a in c.ds.rows("assignments") if a["is_current"]}
    cands = [t for t in c.ds.rows("tickets") if t["is_sensitive"] and t["ticket_id"] in current
             and t["status"] not in ("CANCELLED",) and current[t["ticket_id"]]["team_id"] != "TEAM-01"]
    for t in c.pick(cands, lambda x: x["ticket_id"]):
        asg = current[t["ticket_id"]]
        old = asg["team_id"]
        asg["team_id"] = "TEAM-01"
        asg["routing_reason"] = "Routed to the general HR queue."
        asg["rule_reference"] = "RRL-DEFAULT"
        t["assigned_team_id"] = "TEAM-01"
        c.record("SENSITIVE_IN_GENERAL_QUEUE", "assignments", asg["assignment_id"], t["ticket_id"],
                 "Sensitive ticket sits in the general HR queue (TEAM-01) instead of %s." % old,
                 "Sensitive tickets must be routed to the restricted Employee Relations team (TEAM-06).",
                 "current assignment team changed from %s to TEAM-01" % old, "CRITICAL")


def sla_excludes_business_hours(c: _Ctx) -> None:
    cands = []
    for s in c.ds.rows("slas"):
        wall = s["started_at"] + timedelta(hours=float(s["target_hours"]))
        if (s["total_paused_business_minutes"] == 0 and abs((wall - s["due_at"]).total_seconds()) >= 12 * 3600
                and wall >= s["started_at"]):
            cands.append(s)
    for s in c.pick(cands, lambda x: x["ticket_id"]):
        wall = s["started_at"] + timedelta(hours=float(s["target_hours"]))
        correct = s["due_at"]
        s["due_at"] = wall
        c.record("SLA_EXCLUDES_BUSINESS_HOURS", "slas", s["sla_id"], s["ticket_id"],
                 "SLA due date computed with %.0f calendar hours, ignoring business hours and holidays." % float(s["target_hours"]),
                 "Due date must be %s (business-hours calculation)." % correct.isoformat(),
                 "slas.due_at replaced with started_at + target_hours (wall clock): %s" % wall.isoformat(), "HIGH")


def unsupported_claim(c: _Ctx) -> None:
    cands = [r for r in c.ds.rows("resolutions") if r["resolution_type"] == "ACTION_COMPLETED"]
    claims = ("Verified against company policy: employees are entitled to 30 days of paid leave.",
              "Confirmed per HR policy that the allowance is doubled for all staff.",
              "Verified: the reimbursement limit was raised to 5000 dollars last quarter.",
              "Policy-verified: probation is waived for every internal transfer.",
              "Verified by HR: all employees receive a retention bonus after two years.")
    for i, r in enumerate(c.pick(cands, lambda x: x["ticket_id"])):
        r["resolution_type"] = "POLICY_ANSWER"
        r["resolution_text"] = claims[i % len(claims)]
        r["summary"] = "Verified policy answer"
        r["policy_version_id"] = r["citation_id"] = r["article_id"] = None
        c.record("UNSUPPORTED_CLAIM_AS_VERIFIED", "resolutions", r["resolution_id"], r["ticket_id"],
                 "Claim is presented as verified but no policy version, citation or article supports it.",
                 "A claim may only be presented as verified when it carries a policy source.",
                 "resolution text says 'verified' with all source references null", "CRITICAL")


def missing_employee_context(c: _Ctx) -> None:
    employees = c.ds.index("employees", "employee_id")
    cands = [t for t in c.ds.rows("tickets") if t["requester_id"] in employees
             and employees[t["requester_id"]]["manager_id"] and t["requester_id"] > "EMP-000010"]
    seen: Set[str] = set()
    for t in c.pick(cands, lambda x: x["ticket_id"]):
        if t["requester_id"] in seen:
            continue
        seen.add(t["requester_id"])
        e = employees[t["requester_id"]]
        e["manager_id"], e["job_title"], e["team_id"] = None, None, None
        c.record("MISSING_EMPLOYEE_CONTEXT", "employees", e["employee_id"], t["ticket_id"],
                 "Requester has no manager, job title or team on record.",
                 "Context-dependent answers must request or flag the missing employee context.",
                 "employees.manager_id, job_title and team_id set to NULL", "MEDIUM")


def ambiguous_classification(c: _Ctx) -> None:
    ids = c.ds.extra["category_ids"]
    asked = {e["ticket_id"] for e in c.ds.rows("ticket_events") if e["event_type"] == "CLARIFICATION_REQUESTED"}
    cands = [t for t in c.ds.rows("tickets") if t["status"] in ("CLOSED", "RESOLVED") and not t["is_sensitive"]
             and t["ticket_id"] not in asked and not t["is_ambiguous"]]
    messages = {m["ticket_id"]: m for m in c.ds.rows("messages") if m["sequence_number"] == 1}
    for i, t in enumerate(c.pick(cands, lambda x: x["ticket_id"])):
        subject, body = _AMBIGUOUS_TEXT[i % len(_AMBIGUOUS_TEXT)]
        result = _CLASSIFY.classify(subject, body)
        t["subject"], t["description"] = subject, body
        t["category_id"] = ids.get(result.category, t["category_id"])
        t["classification_confidence"] = min(result.confidence, 0.45)
        t["classification_explanation"] = result.to_dict()
        t["is_ambiguous"] = True
        if t["ticket_id"] in messages:
            messages[t["ticket_id"]]["body"] = body
        c.record("AMBIGUOUS_CLASSIFICATION", "tickets", t["ticket_id"], t["ticket_id"],
                 "Ticket text matches several categories with similar scores.",
                 "Ticket must be flagged ambiguous and a clarification requested instead of silent routing.",
                 "ticket text replaced with multi-topic text; confidence capped at 0.45", "MEDIUM")


def expired_policy(c: _Ctx) -> None:
    info = c.ds.extra["policy_info"]
    retired_versions = sorted((v for v in c.ds.rows("policy_versions") if info[v["policy_id"]]["retired"]
                               and v["status"] == "PUBLISHED"), key=lambda v: v["version_id"])
    if not retired_versions:
        return
    for i, r in enumerate(c.pick(_policy_resolutions(c), lambda x: x["ticket_id"])):
        v = retired_versions[i % len(retired_versions)]
        r["policy_version_id"], r["citation_id"], r["article_id"] = v["version_id"], c.citations.get(v["version_id"]), None
        r["resolution_text"] = _text(v)
        c.record("EXPIRED_POLICY_REFERENCE", "resolutions", r["resolution_id"], r["ticket_id"],
                 "Answer cites %s, a retired policy that is no longer valid." % v["policy_id"],
                 "Retired policies must never be cited; use the active policy for the topic.",
                 "resolution points at version %s of a RETIRED policy" % v["version_id"], "HIGH")


def conflicting_policies(c: _Ctx) -> None:
    info = c.ds.extra["policy_info"]
    v1s = [v for v in c.ds.rows("policy_versions") if v["version_number"] == 1 and v["status"] == "ARCHIVED"
           and info[v["policy_id"]]["scenario"] == "two" and "policy:" + v["policy_id"] not in c.used]
    for v in c.pick(v1s, lambda x: x["policy_id"]):
        v["status"], v["effective_to"] = "PUBLISHED", None
        c.record("CONFLICTING_POLICY_MATCHES", "policy_versions", v["version_id"], None,
                 "Versions 1 and 2 of %s are both published and in force with different values." % v["policy_id"],
                 "Only one version may be in force; the validity engine must flag the conflict.",
                 "v1 set back to PUBLISHED with open-ended effective window", "HIGH")


def missing_policy_source(c: _Ctx) -> None:
    answers = ("Employees get 25 days of leave a year.", "Salary is paid on the 1st of each month.",
               "The company covers the full insurance premium.", "Expenses can be claimed within 90 days.",
               "Probation is two months for everyone.")
    for i, r in enumerate(c.pick(_policy_resolutions(c), lambda x: x["ticket_id"])):
        r["policy_version_id"] = r["citation_id"] = r["article_id"] = None
        r["resolution_text"] = answers[i % len(answers)]
        c.record("MISSING_POLICY_SOURCE", "resolutions", r["resolution_id"], r["ticket_id"],
                 "Policy answer has no policy version, citation or article reference.",
                 "Every POLICY_ANSWER must reference a policy version.",
                 "policy_version_id, citation_id and article_id set to NULL", "HIGH")


def duplicate_message(c: _Ctx) -> None:
    by: Dict[str, List[Dict[str, Any]]] = {}
    for m in c.ds.rows("messages"):
        by.setdefault(m["ticket_id"], []).append(m)
    cands = []
    for tid, msgs in by.items():
        msgs.sort(key=lambda m: m["sequence_number"])
        for a, b in zip(msgs, msgs[1:]):
            if (a["sender_type"] != "SYSTEM" and b["sender_type"] == a["sender_type"]
                    and b["message_type"] == a["message_type"] and a["body"] != b["body"]):
                cands.append((tid, a, b))
                break
    for tid, a, b in c.pick(cands, lambda x: x[0]):
        b["body"], b["sender_user_id"] = a["body"], a["sender_user_id"]
        c.record("DUPLICATE_MESSAGE", "messages", b["message_id"], tid,
                 "Message %s repeats the body of the previous message %s." % (b["message_id"], a["message_id"]),
                 "Consecutive identical messages from the same sender must be detected and suppressed.",
                 "message body and sender copied from the previous message", "LOW")


def invalid_transition(c: _Ctx) -> None:
    limit = REFERENCE_NOW - timedelta(days=2)
    cands = [t for t in c.ds.rows("tickets") if t["status"] == "CLOSED" and t["closed_at"] and t["closed_at"] <= limit]
    for t in c.pick(cands, lambda x: x["ticket_id"]):
        ts = t["closed_at"] + timedelta(days=1)
        c.add_event(t["ticket_id"], "STATUS_CHANGED", "CLOSED", "IN_PROGRESS", ts, {"note": "illegal transition"})
        c.add_audit(event_type="TICKET_IN_PROGRESS", action="TRANSITION", entity_type="tickets", entity_id=t["ticket_id"],
                    actor_user_id=None, actor_role=None, old_values={"status": "CLOSED"},
                    new_values={"status": "IN_PROGRESS"}, ip_address=None, created_at=ts)
        c.record("INVALID_LIFECYCLE_TRANSITION", "ticket_events", t["ticket_id"], t["ticket_id"],
                 "Event history shows CLOSED -> IN_PROGRESS, which the lifecycle forbids.",
                 "CLOSED is terminal; the transition must be rejected.",
                 "STATUS_CHANGED event CLOSED->IN_PROGRESS appended after closure", "HIGH")


def sla_breach(c: _Ctx) -> None:
    limit = REFERENCE_NOW - timedelta(days=4)
    cands = [s for s in c.ds.rows("slas") if s["status"] == "ACTIVE" and s["started_at"] <= limit
             and c.tickets[s["ticket_id"]]["status"] not in ("CANCELLED", "CLOSED", "RESOLVED")]
    for s in c.pick(cands, lambda x: x["ticket_id"]):
        # 4 business-hour target keeps due_at consistent with the business-hours arithmetic.
        s["target_hours"] = 4.0
        due = CALC.add_business_minutes(s["started_at"], 4 * 60 + int(s["total_paused_business_minutes"] or 0))
        s["due_at"], s["status"], s["is_breached"], s["breached_at"] = due, "BREACHED", True, due
        c.add_event(s["ticket_id"], "SLA_BREACHED", None, None, due, {"due_at": due.isoformat()})
        c.record("SLA_BREACH", "slas", s["sla_id"], s["ticket_id"],
                 "Open ticket passed its SLA deadline on %s without resolution." % due.isoformat(),
                 "Breach must be flagged, escalated and shown in the SLA dashboard.",
                 "SLA target set to 4 business hours so the deadline lies in the past while the ticket is open", "HIGH")


def unauthorized_access(c: _Ctx) -> None:
    ctx = c.ds.extra["employee_ctx"]
    plain = sorted(v["user_id"] for v in ctx.values() if v["role"] == "EMPLOYEE")
    sensitive = [t for t in c.ds.rows("tickets") if t["is_sensitive"]]
    for i, t in enumerate(c.pick(sensitive, lambda x: x["ticket_id"])):
        actor = plain[(i * 7 + 3) % len(plain)]
        ts = t["created_at"] + timedelta(hours=5, minutes=i)
        c.add_audit(event_type="ACCESS_DENIED", action="ACCESS_DENIED", entity_type="tickets", entity_id=t["ticket_id"],
                    actor_user_id=actor, actor_role="EMPLOYEE", old_values=None,
                    new_values={"reason": "not authorised for sensitive ticket"}, ip_address="10.0.0.%d" % (20 + i),
                    created_at=ts)
        c.record("UNAUTHORIZED_ACCESS_ATTEMPT", "audit_logs", t["ticket_id"], t["ticket_id"],
                 "User %s attempted to open a sensitive ticket they may not see." % actor,
                 "Access must be denied and the attempt audited; no ticket content may be returned.",
                 "ACCESS_DENIED audit row for a non-privileged user on a sensitive ticket", "HIGH")


_ORDER = (obsolete_policy, sensitive_in_general, sla_excludes_business_hours, unsupported_claim,
          ambiguous_classification, expired_policy, conflicting_policies, missing_policy_source,
          missing_employee_context, duplicate_message, invalid_transition, sla_breach, unauthorized_access)


def inject_anomalies(ds: Dataset) -> List[Dict[str, Any]]:
    c = _Ctx(ds)
    for step in _ORDER:
        step(c)
    c.register.sort(key=lambda a: a["issue_id"])
    return c.register
