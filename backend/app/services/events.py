"""Helper for writing append-only ticket history rows."""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.ticket import TicketEvent
from app.services.audit_service import jsonable
from app.services.ids import next_id


def record_ticket_event(
    db: Session,
    ticket_id: str,
    event_type: str,
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    created_at: Optional[datetime] = None,
) -> TicketEvent:
    values: Dict[str, Any] = dict(
        event_id=next_id(db, TicketEvent.event_id, "TEV-", 6),
        ticket_id=ticket_id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        actor_user_id=actor_user_id,
        details=jsonable(details) if details is not None else None,
    )
    if created_at is not None:
        values["created_at"] = created_at
    event = TicketEvent(**values)
    db.add(event)
    db.flush()
    return event
