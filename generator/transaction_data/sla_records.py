"""SLA rows and pause events, derived from the simulated ticket plans.

``compute_due`` is shared with the ticket simulator so that resolution times are chosen
consistently with the deadline, and with the validators (same arithmetic, same engine).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from generator.config import REFERENCE_NOW
from generator.master_data.departments import CALENDAR_ID
from generator.utils.calendar_util import CALC, CALENDAR
from generator.utils.dataset import Dataset
from app.rules.sla_engine import calculate_sla_deadline


def compute_due(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Deadline for a plan: engine deadline shifted by business minutes spent paused."""
    deadline = calculate_sla_deadline(
        plan["created_at"], plan["initial_category"], plan["priority"], plan["sensitive"], None, CALENDAR
    )
    due = deadline.due_at
    paused_minutes = 0
    pause = plan.get("pause")
    if pause and pause.get("resumed_at") is not None:
        paused_minutes = CALC.elapsed_business_minutes(pause["paused_at"], pause["resumed_at"])
        due = CALC.add_business_minutes(due, paused_minutes)
    return {
        "policy": deadline.sla_policy,
        "target_hours": deadline.target_hours,
        "base_due": deadline.due_at,
        "due_at": due,
        "paused_minutes": paused_minutes,
        "first_response_target_hours": deadline.first_response_target_hours,
        "first_response_due_at": deadline.first_response_due_at,
    }


def compute_sla(plan: Dict[str, Any], now: datetime = REFERENCE_NOW) -> Dict[str, Any]:
    info = compute_due(plan)
    due = info["due_at"]
    final = plan["status"]
    pause = plan.get("pause")
    open_pause = bool(pause) and pause["resumed_at"] is None
    resolved: Optional[datetime] = None
    breached = False
    breach_event = False
    if final in ("RESOLVED", "CLOSED"):
        resolved = plan["resolved_at"]
        breached = resolved > due
        status = "BREACHED" if breached else "MET"
    elif open_pause:
        status = "PAUSED"
    else:
        first_resolved = plan.get("first_resolved_at")
        was_late = first_resolved is not None and first_resolved > due
        over = final != "CANCELLED" and now > due
        breached = was_late or over
        breach_event = over
        status = "BREACHED" if breached else "ACTIVE"
    info.update({
        "status": status,
        "is_breached": breached,
        "breached_at": due if breached else None,
        "resolved_at": resolved,
        "breach_event": breach_event,
    })
    return info


def generate_sla_records(ds: Dataset) -> None:
    pause_rows: List[Dict[str, Any]] = []
    for plan in ds.extra["plans"]:
        sla = plan["sla"]
        sid = "SLA-%s" % plan["ticket_id"]
        updated = plan["steps"][-1]["ts"]
        ds.add("slas", sla_id=sid, ticket_id=plan["ticket_id"], calendar_id=CALENDAR_ID,
               sla_policy=sla["policy"], priority=plan["priority"], target_hours=sla["target_hours"],
               first_response_target_hours=sla["first_response_target_hours"], started_at=plan["created_at"],
               due_at=sla["due_at"], first_response_due_at=sla["first_response_due_at"],
               first_response_at=plan.get("first_response_at"), resolved_at=sla["resolved_at"],
               total_paused_business_minutes=sla["paused_minutes"], status=sla["status"],
               is_breached=sla["is_breached"], breached_at=sla["breached_at"],
               created_at=plan["created_at"], updated_at=updated)
        pause = plan.get("pause")
        if pause:
            pause_rows.append({"sla_id": sid, "reason": pause["reason"], "paused_at": pause["paused_at"],
                               "resumed_at": pause["resumed_at"],
                               "business_minutes_paused": sla["paused_minutes"] if pause["resumed_at"] else None})
    pause_rows.sort(key=lambda r: (r["paused_at"], r["sla_id"]))
    for number, row in enumerate(pause_rows, start=1):
        ds.add("sla_pause_events", pause_id="PAU-%06d" % number, paused_by=None,
               created_at=row["paused_at"], **row)
