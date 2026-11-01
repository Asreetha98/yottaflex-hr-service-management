"""Append-only audit log."""

from typing import Optional

from sqlalchemy import JSON, CheckConstraint, String, event
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import AUDIT_ACTIONS, sql_in
from app.models.base import Base, UTCDateTime, utcnow


class AuditLog(Base):
    """Immutable record of a business event.

    ``actor_user_id`` is intentionally not a foreign key: audit history must
    survive any later removal of the user row.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (CheckConstraint(sql_in("action", AUDIT_ACTIONS), name="action_valid"),)

    event_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    actor_user_id: Mapped[Optional[str]] = mapped_column(String(50))
    actor_role: Mapped[Optional[str]] = mapped_column(String(50))
    old_values: Mapped[Optional[dict]] = mapped_column(JSON)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    created_at = mapped_column(UTCDateTime(), default=utcnow, index=True, nullable=False)


class AuditLogImmutableError(RuntimeError):
    """Raised when code attempts to modify or delete an audit row."""


@event.listens_for(AuditLog, "before_update")
def _reject_audit_update(_mapper, _connection, _target):
    raise AuditLogImmutableError("audit_logs rows are append-only and cannot be updated")


@event.listens_for(AuditLog, "before_delete")
def _reject_audit_delete(_mapper, _connection, _target):
    raise AuditLogImmutableError("audit_logs rows are append-only and cannot be deleted")
