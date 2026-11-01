"""Ticket simulator: deterministic lifecycles for every ticket.

Each ticket is first *planned* as a time-ordered list of steps (``Planner``), then
*committed* to the dataset tables (``_commit_plan``). The planner replays the same
lifecycle state machine the platform enforces (``ALLOWED_TRANSITIONS``), never emits a
timestamp after ``REFERENCE_NOW`` (a ticket simply stops at the state it had reached),
and derives the final status from that replay rather than drawing it independently.

The stored decisions (category, sensitivity, priority, routing, clarification) come from
the production rule engines; the *ground truth* labels live separately in ``plan["truth"]``
and are never written to an operational table.
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from generator.config import DATA_START_DATE, REFERENCE_NOW, stage_rng
from generator.master_data.departments import TEAMS
from generator.transaction_data.resolutions import build_spec, generate_resolutions
from generator.transaction_data.sla_records import compute_due, compute_sla, generate_sla_records
from generator.transaction_data.ticket_templates import REPLIES, compose
from generator.utils.calendar_util import CALC
from generator.utils.dataset import Dataset
from generator.utils.id_generator import audit_id, message_id, ticket_id
from app.constants import ALLOWED_TRANSITIONS
from app.rules.classification_engine import ClassificationEngine
from app.rules.clarification_engine import ClarificationEngine
from app.rules.routing_engine import RoutingEngine
from app.rules.sensitive_routing_engine import SensitiveRoutingEngine
from app.rules.sla_engine import derive_priority

_CLASSIFY = ClassificationEngine()
_SENSITIVE = SensitiveRoutingEngine()
_ROUTE = RoutingEngine()
_CLARIFY = ClarificationEngine()

_TEAM_MAP = {(team_type, level): team for team, _, _, team_type, level, _ in TEAMS}
_START = datetime.combine(DATA_START_DATE, datetime.min.time()).replace(tzinfo=timezone.utc)

_TARGETS = (("CLOSED", 64), ("RESOLVED", 12), ("IN_PROGRESS", 6), ("ASSIGNED", 4), ("AWAITING", 4),
            ("ESCALATED", 3), ("CANCELLED", 4), ("REOPENED", 3))
_AGENT_REPLIES = (
    "Thank you for contacting HR. We have reviewed your request and are working on it.",
    "Your request has been received and is being processed by the specialist team.",
    "We are checking the details with the relevant team and will update you shortly.",
    "Thanks for your patience. We are progressing your request.",
)
_EMPLOYEE_FOLLOWUPS = (
    "Thanks, please let me know once this is done.",
    "Just checking whether there is any update on my request.",
    "I can share any additional document you need.",
    "Understood, thank you for the update.",
)
_INTERNAL_NOTES = (
    "Verified the employee record; details match.",
    "Checked the applicable policy version before replying.",
    "Waiting on confirmation from the owning team.",
)
_CLOSE_TEXT = (
    "Your HR request has been resolved. Please reply if you need anything further.",
    "We have addressed your query and are closing this ticket.",
)


def _weighted(rng: random.Random, options: Any) -> str:
    total = sum(w for _, w in options)
    pick = rng.uniform(0, total)
    running = 0.0
    for value, weight in options:
        running += weight
        if pick <= running:
            return value
    return options[-1][0]


class _Stop(Exception):
    """Raised when the next event would fall after the reference clock."""


class Planner:
    """Builds one ticket's step list while replaying the lifecycle state machine."""

    def __init__(self, created_at: datetime) -> None:
        self.steps: List[Dict[str, Any]] = []
        self.ts = created_at
        self.state = "NEW"
        self.first_response_at: Optional[datetime] = None
        self.resolved_at: Optional[datetime] = None
        self.first_resolved_at: Optional[datetime] = None

    def advance(self, minutes: int) -> None:
        self.ts = CALC.add_business_minutes(self.ts, max(1, int(minutes)))

    def go(self, target: str, kind: str, **extra: Any) -> None:
        if self.ts > REFERENCE_NOW:
            raise _Stop()
        if target not in ALLOWED_TRANSITIONS[self.state]:
            raise AssertionError("illegal transition %s -> %s" % (self.state, target))
        self.steps.append({"kind": kind, "ts": self.ts, "from": self.state, "to": target, **extra})
        self.state = target

    def note(self, kind: str, **extra: Any) -> None:
        if self.ts > REFERENCE_NOW:
            raise _Stop()
        self.steps.append({"kind": kind, "ts": self.ts, "from": self.state, "to": self.state, **extra})


def _raw_created_at(rng: random.Random) -> datetime:
    span = int((REFERENCE_NOW - _START).total_seconds() * 0.985)
    for _ in range(4):
        moment = _START + timedelta(seconds=rng.randint(0, span))
        if moment.weekday() < 5 or rng.random() < 0.08:
            return moment
    return moment


def _plan_ticket(rng: random.Random, ds: Dataset, number: int) -> Dict[str, Any]:
    ctx = ds.extra["employee_ctx"]
    created_at = _raw_created_at(rng)
    eligible = [e for e, c in ctx.items() if c["role"] in ("EMPLOYEE", "MANAGER") and c["status"] != "TERMINATED"
                and c["hire_date"] <= created_at.date()]
    requester = eligible[rng.randrange(len(eligible))]
    requester_user = ctx[requester]["user_id"]

    truth = compose(rng, requester.split("-")[-1])
    classification = _CLASSIFY.classify(truth["subject"], truth["description"])
    sensitivity = _SENSITIVE.detect(truth["subject"], truth["description"])
    sensitive = sensitivity.is_sensitive
    priority = derive_priority(truth["subject"], truth["description"], sensitive)
    decision = _CLARIFY.needs_clarification(truth["subject"], truth["description"], classification, sensitive)
    initial_category = classification.category

    target = _weighted(rng, _TARGETS)
    reopen_requested = target == "REOPENED" or (target in ("CLOSED", "RESOLVED") and rng.random() < 0.05)
    plan_state: Dict[str, Any] = {"pause": None, "category": classification, "route": None, "team": None}
    p = Planner(created_at)
    staff = ds.extra["staff"]

    def resolver_for(team: Optional[str]) -> str:
        pool = [s for s in staff if s["active"] and s["role"] in ("HR_PARTNER", "ADMIN")
                and (not sensitive or s["can_view_sensitive"])]
        same = [s for s in pool if s["team_id"] == team]
        pool = same or pool
        return pool[rng.randrange(len(pool))]["user_id"]

    resolver = resolver_for(None)
    partial = {"created_at": created_at, "initial_category": initial_category, "priority": priority,
               "sensitive": sensitive, "pause": None}

    def route_to(result: Any) -> str:
        route = _ROUTE.determine_assignment(type("T", (), {"ticket_id": None})(), result, sensitivity)
        plan_state["route"] = route
        return _TEAM_MAP[(route.assigned_team, route.support_level)]

    try:
        p.go("CLASSIFIED", "classify")
        if target == "CANCELLED" and rng.random() < 0.5:
            p.advance(rng.randint(30, 600))
            p.go("CANCELLED", "cancel")
            raise _Stop()

        clarify = decision.needs_clarification and (target != "ASSIGNED") and rng.random() < 0.85
        if clarify:
            p.advance(rng.randint(5, 60))
            p.go("AWAITING_CLARIFICATION", "clarify", message=decision.message,
                 reasons=decision.reasons, missing=decision.missing_fields)
            paused_at = p.ts
            plan_state["pause"] = {"reason": "AWAITING_CLARIFICATION", "paused_at": paused_at, "resumed_at": None}
            if target == "AWAITING":
                raise _Stop()
            p.advance(rng.randint(120, 1500))
            reply = REPLIES[truth["expected_category"]].format(**truth["slots"])
            p.note("reply", message=reply)
            plan_state["pause"]["resumed_at"] = p.ts
            after = _CLASSIFY.classify(truth["subject"], truth["description"] + " " + reply)
            plan_state["category"] = after
            team = route_to(after)
            plan_state["team"] = team
            p.advance(1)
            p.go("ASSIGNED", "assign", team=team, reason=plan_state["route"].routing_reason,
                 rule=plan_state["route"].rule_reference, atype="AUTO")
        else:
            team = route_to(classification)
            plan_state["team"] = team
            p.advance(rng.randint(1, 45))
            p.go("ASSIGNED", "assign", team=team, reason=plan_state["route"].routing_reason,
                 rule=plan_state["route"].rule_reference, atype="AUTO")
        resolver = resolver_for(plan_state["team"])
        partial["pause"] = plan_state["pause"]

        if sensitive:
            p.go("ESCALATED", "escalate", from_team=plan_state["team"], to_team=plan_state["team"], level="L2",
                 reason_code="SENSITIVE_CASE", reason="Sensitive case detected: " + ", ".join(sensitivity.matched_patterns),
                 reassign=False, by=None)
            if target == "ESCALATED":
                raise _Stop()
        if target == "ASSIGNED":
            raise _Stop()

        p.advance(rng.randint(15, 240))
        p.go("IN_PROGRESS", "start", actor=resolver)
        p.first_response_at = p.ts
        if rng.random() < 0.3:
            p.advance(rng.randint(5, 60))
            p.note("internal", message=rng.choice(_INTERNAL_NOTES), actor=resolver)
        if target == "IN_PROGRESS":
            raise _Stop()

        if not sensitive and (target == "ESCALATED" or rng.random() < 0.04):
            p.advance(rng.randint(30, 240))
            code = "SLA_BREACH" if rng.random() < 0.4 else "MANUAL"
            p.go("ESCALATED", "escalate", from_team=plan_state["team"], to_team=_TEAM_MAP[("HR_GENERAL", "L2")],
                 level="L2", reason_code=code, reason="Escalated to HR Operations (L2)", reassign=True, by=resolver)
            if target == "ESCALATED":
                raise _Stop()
            p.advance(rng.randint(30, 300))
            p.go("IN_PROGRESS", "resume", actor=resolver)

        # Resolution time is placed relative to the engine deadline so SLA outcomes reconcile.
        due = compute_due(partial)
        remaining = CALC.elapsed_business_minutes(p.ts, due["due_at"])
        if rng.random() < 0.88 and remaining > 40:
            p.advance(max(15, int(remaining * rng.uniform(0.12, 0.95))))
        elif rng.random() < 0.88:
            p.ts = CALC.add_business_minutes(max(p.ts, due["due_at"]), int(due["target_hours"] * 60 * rng.uniform(0.05, 0.8)) + 1)
        else:
            p.advance(rng.randint(15, 90))

        spec = build_spec(rng, ds, {"truth": truth, "requester": requester, "created_at": created_at,
                                    "sensitive": sensitive}, resolver)
        p.go("RESOLVED", "resolve", details={"resolution": spec}, actor=resolver)
        p.resolved_at = p.first_resolved_at = p.ts
        if reopen_requested:
            spec["was_reopened"] = True
            p.advance(rng.randint(60, 900))
            p.go("REOPENED", "reopen", actor=requester_user, message="The issue is still not resolved for me.")
            p.resolved_at = None
            if target == "REOPENED":
                raise _Stop()
            p.advance(rng.randint(20, 240))
            p.go("IN_PROGRESS", "resume", actor=resolver)
            p.advance(rng.randint(60, 600))
            spec2 = build_spec(rng, ds, {"truth": truth, "requester": requester, "created_at": created_at,
                                         "sensitive": sensitive}, resolver)
            p.go("RESOLVED", "resolve", details={"resolution": spec2}, actor=resolver)
            p.resolved_at = p.ts
        if target == "RESOLVED":
            raise _Stop()
        p.advance(rng.randint(30, 1200))
        p.go("CLOSED", "close", actor=resolver)
    except _Stop:
        pass

    after = plan_state["category"]
    return {
        "ticket_id": ticket_id(number), "requester": requester, "requester_user": requester_user, "resolver": resolver,
        "subject": truth["subject"], "description": truth["description"], "channel": truth["channel"],
        "truth": truth, "created_at": created_at, "initial_category": initial_category, "priority": priority,
        "sensitive": sensitive, "sensitive_patterns": sensitivity.matched_patterns, "decision": decision,
        "category": after.category, "confidence": after.confidence, "explanation": after.to_dict(),
        "is_ambiguous": after.is_ambiguous, "team": plan_state["team"], "status": p.state,
        "resolved_at": p.resolved_at, "first_resolved_at": p.first_resolved_at,
        "first_response_at": p.first_response_at, "pause": plan_state["pause"], "steps": p.steps,
        "reopen_count": sum(1 for s in p.steps if s["kind"] == "reopen"),
        "closed_at": p.ts if p.state == "CLOSED" else None,
    }


_MESSAGE_KINDS = ("classify", "clarify", "reply", "agent", "internal", "followup", "reopen", "close")
_TRANSITION_KINDS = ("classify", "clarify", "assign", "start", "resume", "escalate", "resolve", "reopen", "close",
                     "cancel")
_MAX_EXCHANGES = 14


def _top_up_messages(plans: List[Dict[str, Any]], target: int) -> None:
    """Add agent/employee exchanges right after work starts until exactly ``target`` messages exist.

    Exchanges are spaced 30 seconds apart (at most 14 per ticket = 14 minutes, shorter than the
    15-minute minimum before resolution) and are never placed after the reference clock.
    """
    total = sum(1 for p in plans for s in p["steps"] if s["kind"] in _MESSAGE_KINDS)
    eligible = [p for p in plans if any(s["kind"] == "start" for s in p["steps"])]
    deficit = target - total
    if not eligible or deficit <= 0:
        return
    added = {p["ticket_id"]: 0 for p in eligible}
    start_ts = {p["ticket_id"]: next(s["ts"] for s in p["steps"] if s["kind"] == "start") for p in eligible}
    index = 0
    stalled = 0
    while deficit > 0 and stalled < len(eligible):
        plan = eligible[index % len(eligible)]
        index += 1
        tid = plan["ticket_id"]
        n = added[tid] + 1
        if n > _MAX_EXCHANGES or start_ts[tid] + timedelta(seconds=60 * n) > REFERENCE_NOW:
            stalled += 1
            continue
        stalled = 0
        added[tid] = n
        base = start_ts[tid]
        plan["steps"].append({"kind": "agent", "ts": base + timedelta(seconds=60 * n - 30), "from": "IN_PROGRESS",
                              "to": "IN_PROGRESS", "actor": plan["resolver"],
                              "message": _AGENT_REPLIES[(index + n) % len(_AGENT_REPLIES)]})
        deficit -= 1
        if deficit > 0:
            plan["steps"].append({"kind": "followup", "ts": base + timedelta(seconds=60 * n), "from": "IN_PROGRESS",
                                  "to": "IN_PROGRESS", "actor": plan["requester_user"],
                                  "message": _EMPLOYEE_FOLLOWUPS[(index + n) % len(_EMPLOYEE_FOLLOWUPS)]})
            deficit -= 1
    for plan in eligible:  # stable sort keeps same-timestamp steps in their planned order
        plan["steps"].sort(key=lambda s: s["ts"])


def _commit_plan(ds: Dataset, plan: Dict[str, Any], c: Dict[str, int], category_ids: Dict[str, str]) -> None:
    tid = plan["ticket_id"]
    row = ds.add("tickets", ticket_id=tid, requester_id=plan["requester"], subject=plan["subject"],
                 description=plan["description"], category_id=category_ids[plan["category"]],
                 priority=plan["priority"], status=plan["status"], channel=plan["channel"],
                 is_sensitive=plan["sensitive"], access_level="RESTRICTED" if plan["sensitive"] else "STANDARD",
                 sensitive_patterns=plan["sensitive_patterns"] or None, classification_confidence=plan["confidence"],
                 classification_explanation=plan["explanation"], is_ambiguous=plan["is_ambiguous"],
                 assigned_team_id=None, assigned_user_id=None, reopen_count=plan["reopen_count"],
                 first_response_at=plan["first_response_at"], resolved_at=plan["resolved_at"],
                 closed_at=plan["closed_at"], created_at=plan["created_at"], is_deleted=False, deleted_at=None,
                 updated_at=plan["steps"][-1]["ts"] if plan["steps"] else plan["created_at"])
    seq = {"msg": 0}
    current_asg: Dict[str, Any] = {}

    def message(user: Optional[str], sender: str, mtype: str, body: str, internal: bool, ts: datetime) -> None:
        seq["msg"] += 1
        ds.add("messages", message_id=message_id(tid, seq["msg"]), ticket_id=tid, sequence_number=seq["msg"],
               sender_user_id=user, sender_type=sender, message_type=mtype, is_internal=internal, body=body,
               created_at=ts, updated_at=ts, is_deleted=False, deleted_at=None)

    def event(etype: str, ts: datetime, f: Optional[str] = None, t: Optional[str] = None,
              actor: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        c["tev"] += 1
        ds.add("ticket_events", event_id="TEV-%06d" % c["tev"], ticket_id=tid, event_type=etype, from_status=f,
               to_status=t, actor_user_id=actor, details=details, created_at=ts)

    def audit(etype: str, action: str, ts: datetime, actor: Optional[str], old: Any = None, new: Any = None) -> None:
        c["evt"] += 1
        ds.add("audit_logs", event_id=audit_id(c["evt"]), event_type=etype, action=action, entity_type="tickets",
               entity_id=tid, actor_user_id=actor, actor_role=None, old_values=old, new_values=new,
               ip_address=None, created_at=ts)

    def retire_previous(ts: datetime) -> None:
        prev = current_asg.get("_row")
        if prev is not None:
            prev["is_current"] = False
            prev["unassigned_at"] = ts

    for s in plan["steps"]:
        ts, kind = s["ts"], s["kind"]
        if kind == "classify":
            event("CREATED", plan["created_at"], None, "NEW", plan["requester_user"], {"channel": plan["channel"]})
            audit("TICKET_CREATED", "CREATE", plan["created_at"], plan["requester_user"], None,
                  {"subject": plan["subject"], "requester_id": plan["requester"]})
            message(plan["requester_user"], "EMPLOYEE", "PUBLIC", plan["description"], False, plan["created_at"])
            event("CLASSIFIED", ts, "NEW", "CLASSIFIED", None,
                  {"category": plan["initial_category"], "confidence": plan["confidence"],
                   "sensitive": plan["sensitive"]})
        elif kind == "clarify":
            event("CLARIFICATION_REQUESTED", ts, s["from"], s["to"], None,
                  {"reasons": s["reasons"], "missing_fields": s["missing"]})
            message(None, "SYSTEM", "CLARIFICATION_REQUEST", s["message"], False, ts)
            event("SLA_PAUSED", ts, None, None, None, {"reason": "AWAITING_CLARIFICATION"})
        elif kind == "reply":
            message(plan["requester_user"], "EMPLOYEE", "CLARIFICATION_RESPONSE", s["message"], False, ts)
            event("CLARIFICATION_RECEIVED", ts, None, None, plan["requester_user"])
            event("SLA_RESUMED", ts, None, None, plan["requester_user"], {})
        elif kind == "assign":
            retire_previous(ts)
            current_asg.clear()
            c["asg"] += 1
            new = ds.add("assignments", assignment_id="ASG-%06d" % c["asg"], ticket_id=tid, team_id=s["team"],
                         assigned_user_id=None, assigned_by=None, assignment_type="AUTO", routing_reason=s["reason"],
                         rule_reference=s["rule"], is_current=True, assigned_at=ts, unassigned_at=None, created_at=ts)
            current_asg["_row"] = new
            row["assigned_team_id"] = s["team"]
            event("ASSIGNED", ts, s["from"], s["to"], None, {"team_id": s["team"], "rule": s["rule"]})
        elif kind == "start":
            event("STATUS_CHANGED", ts, s["from"], s["to"], s.get("actor"))
        elif kind == "internal":
            message(s["actor"], "AGENT", "INTERNAL_NOTE", s["message"], True, ts)
            event("MESSAGE_ADDED", ts, None, None, s["actor"], {"internal": True})
        elif kind == "agent":
            message(s["actor"], "AGENT", "PUBLIC", s["message"], False, ts)
            event("MESSAGE_ADDED", ts, None, None, s["actor"], {"internal": False})
        elif kind == "followup":
            message(s["actor"], "EMPLOYEE", "PUBLIC", s["message"], False, ts)
            event("MESSAGE_ADDED", ts, None, None, s["actor"], {"internal": False})
        elif kind == "escalate":
            c["esc"] += 1
            resumed = None
            ds.add("escalations", escalation_id="ESC-%06d" % c["esc"], ticket_id=tid, from_team_id=s["from_team"],
                   to_team_id=s["to_team"], escalation_level=s["level"], reason_code=s["reason_code"],
                   reason=s["reason"], escalated_by=s.get("by"), escalated_at=ts, status="OPEN", resolved_at=resumed,
                   created_at=ts, updated_at=ts)
            if s["reassign"]:
                retire_previous(ts)
                c["asg"] += 1
                new = ds.add("assignments", assignment_id="ASG-%06d" % c["asg"], ticket_id=tid, team_id=s["to_team"],
                             assigned_user_id=None, assigned_by=s.get("by"), assignment_type="ESCALATION",
                             routing_reason="Escalated: " + s["reason"], rule_reference=None, is_current=True,
                             assigned_at=ts, unassigned_at=None, created_at=ts)
                current_asg["_row"] = new
                row["assigned_team_id"] = s["to_team"]
            event("ESCALATED", ts, s["from"], s["to"], s.get("by"),
                  {"reason_code": s["reason_code"], "to_team": s["to_team"], "level": s["level"]})
        elif kind == "resume":
            event("STATUS_CHANGED", ts, s["from"], s["to"], s.get("actor"))
        elif kind == "resolve":
            event("RESOLVED", ts, s["from"], s["to"], s["actor"], {"resolution_type": s["details"]["resolution"]["resolution_type"]})
        elif kind == "reopen":
            message(s["actor"], "EMPLOYEE", "PUBLIC", s["message"], False, ts)
            event("REOPENED", ts, s["from"], s["to"], s["actor"], {"reason": s["message"]})
        elif kind == "close":
            event("CLOSED", ts, s["from"], s["to"], s["actor"])
            message(s["actor"], "AGENT", "PUBLIC", _CLOSE_TEXT[plan["reopen_count"] % len(_CLOSE_TEXT)], False, ts)
        elif kind == "cancel":
            event("CANCELLED", ts, s["from"], s["to"], plan["requester_user"])
        if kind in _TRANSITION_KINDS:  # emitted after the kind block so CREATED precedes CLASSIFIED
            audit("TICKET_%s" % s["to"], "TRANSITION", ts, s.get("actor"), {"status": s["from"]}, {"status": s["to"]})
    if plan["sla"]["breach_event"]:
        event("SLA_BREACHED", plan["sla"]["due_at"], None, None, None, {"due_at": plan["sla"]["due_at"].isoformat()})


def _resolve_escalations(ds: Dataset) -> None:
    """An escalation is RESOLVED when the ticket later left the ESCALATED state."""
    by_ticket: Dict[str, List[Dict[str, Any]]] = {}
    for esc in ds.rows("escalations"):
        by_ticket.setdefault(esc["ticket_id"], []).append(esc)
    events: Dict[str, List[Dict[str, Any]]] = {}
    for ev in ds.rows("ticket_events"):
        if ev["event_type"] == "STATUS_CHANGED" and ev["from_status"] == "ESCALATED":
            events.setdefault(ev["ticket_id"], []).append(ev)
    for tid, escs in by_ticket.items():
        leaves = sorted(events.get(tid, []), key=lambda e: e["created_at"])
        for esc in escs:
            later = [e for e in leaves if e["created_at"] >= esc["escalated_at"]]
            if later:
                esc["status"] = "RESOLVED"
                esc["resolved_at"] = later[0]["created_at"]
                esc["updated_at"] = later[0]["created_at"]


def _renumber(ds: Dataset, table: str, column: str, time_col: str, fmt: str) -> None:
    rows = ds.rows(table)
    order = sorted(range(len(rows)), key=lambda i: (rows[i][time_col], i))
    ds.tables[table] = [rows[i] for i in order]
    for number, row in enumerate(ds.tables[table], start=1):
        row[column] = fmt % number


def generate_tickets(ds: Dataset) -> None:
    rng = stage_rng("tickets")
    plans: List[Dict[str, Any]] = []
    for number in range(1, ds.size.tickets + 1):
        plan = _plan_ticket(rng, ds, number)
        plans.append(plan)
    _top_up_messages(plans, ds.size.messages)
    for plan in plans:
        plan["sla"] = compute_sla(plan)
    ds.extra["plans"] = plans

    counters = {"tev": 0, "asg": 0, "esc": 0, "evt": 0}
    category_ids = ds.extra["category_ids"]
    for plan in plans:
        _commit_plan(ds, plan, counters, category_ids)
    _generate_logins(ds, counters)
    generate_sla_records(ds)
    generate_resolutions(ds)
    _resolve_escalations(ds)
    _renumber(ds, "ticket_events", "event_id", "created_at", "TEV-%06d")
    _renumber(ds, "assignments", "assignment_id", "assigned_at", "ASG-%06d")
    _renumber(ds, "escalations", "escalation_id", "escalated_at", "ESC-%06d")
    _renumber(ds, "audit_logs", "event_id", "created_at", "EVT-%06d")


def _generate_logins(ds: Dataset, c: Dict[str, int]) -> None:
    rng = stage_rng("logins")
    staff = [s for s in ds.extra["staff"] if s["active"]]
    span = int((REFERENCE_NOW - _START).total_seconds())
    for _ in range(ds.size.login_events):
        user = staff[rng.randrange(len(staff))]
        ts = _START + timedelta(seconds=rng.randint(0, span))
        c["evt"] += 1
        ds.add("audit_logs", event_id=audit_id(c["evt"]), event_type="LOGIN_SUCCESS", action="LOGIN",
               entity_type="user_accounts", entity_id=user["user_id"], actor_user_id=user["user_id"],
               actor_role=user["role"], old_values=None, new_values=None, ip_address=None, created_at=ts)
