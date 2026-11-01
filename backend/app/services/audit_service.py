"""Append-only audit trail service."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.base import utcnow
from app.models.user import UserAccount
from app.services.ids import next_id


def jsonable(value: Any) -> Any:
    """Convert values to something the JSON column can store."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(v) for v in value]
    return value


class AuditService:
    """Only ``record`` writes; there is intentionally no update or delete path."""

    def record(
        self,
        db: Session,
        event_type: str,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        actor: Optional[UserAccount] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        created_at: Optional[datetime] = None,
        actor_user_id: Optional[str] = None,
    ) -> AuditLog:
        role = ",".join(actor.role_names)[:50] if actor is not None else None
        entry = AuditLog(
            event_id=next_id(db, AuditLog.event_id, "EVT-", 6),
            event_type=event_type,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor.user_id if actor is not None else actor_user_id,
            actor_role=role,
            old_values=jsonable(old_values) if old_values is not None else None,
            new_values=jsonable(new_values) if new_values is not None else None,
            ip_address=ip_address,
            created_at=created_at or utcnow(),
        )
        db.add(entry)
        db.flush()
        return entry

    def list_events(
        self,
        db: Session,
        event_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[AuditLog], int]:
        query = db.query(AuditLog)
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        if entity_id:
            query = query.filter(AuditLog.entity_id == entity_id)
        if actor_user_id:
            query = query.filter(AuditLog.actor_user_id == actor_user_id)
        total = query.count()
        items = (
            query.order_by(AuditLog.created_at.desc(), AuditLog.event_id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total
