"""Ticketing: Ticket, Message, TicketEvent, Assignment, Escalation."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import (
    ACCESS_LEVELS,
    ASSIGNMENT_TYPES,
    ESCALATION_LEVELS,
    ESCALATION_REASONS,
    ESCALATION_STATUSES,
    MESSAGE_SENDER_TYPES,
    MESSAGE_TYPES,
    PRIORITIES,
    TICKET_CHANNELS,
    TICKET_EVENT_TYPES,
    TICKET_STATUSES,
    sql_in,
)
from app.models.base import Base, CreatedAtMixin, SoftDeleteMixin, TimestampMixin, UTCDateTime


class Ticket(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(sql_in("priority", PRIORITIES), name="priority_valid"),
        CheckConstraint(sql_in("status", TICKET_STATUSES), name="status_valid"),
        CheckConstraint(sql_in("channel", TICKET_CHANNELS), name="channel_valid"),
        CheckConstraint(sql_in("access_level", ACCESS_LEVELS), name="access_level_valid"),
        CheckConstraint("reopen_count >= 0", name="reopen_count_non_negative"),
        CheckConstraint(
            "classification_confidence IS NULL OR "
            "(classification_confidence >= 0 AND classification_confidence <= 1)",
            name="confidence_range",
        ),
        CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= created_at", name="resolved_after_created"
        ),
        CheckConstraint(
            "closed_at IS NULL OR resolved_at IS NULL OR closed_at >= resolved_at",
            name="closed_after_resolved",
        ),
    )

    ticket_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    requester_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("employees.employee_id"), index=True, nullable=False
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("categories.category_id"), index=True
    )
    priority: Mapped[str] = mapped_column(String(2), default="P3", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="NEW", index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="PORTAL", nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    access_level: Mapped[str] = mapped_column(String(20), default="STANDARD", nullable=False)
    sensitive_patterns: Mapped[Optional[list]] = mapped_column(JSON)
    classification_confidence: Mapped[Optional[float]] = mapped_column(Float)
    classification_explanation: Mapped[Optional[dict]] = mapped_column(JSON)
    is_ambiguous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assigned_team_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("teams.team_id"), index=True
    )
    assigned_user_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("user_accounts.user_id")
    )
    reopen_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_response_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    closed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())

    requester = relationship("Employee", foreign_keys=[requester_id])
    category = relationship("Category", foreign_keys=[category_id])

    @property
    def category_code(self) -> Optional[str]:
        return self.category.code if self.category is not None else None

    assigned_team = relationship("Team", foreign_keys=[assigned_team_id])
    messages: Mapped[List["Message"]] = relationship(
        back_populates="ticket", order_by="Message.sequence_number"
    )
    events: Mapped[List["TicketEvent"]] = relationship(
        back_populates="ticket", order_by="TicketEvent.created_at"
    )
    assignments: Mapped[List["Assignment"]] = relationship(
        back_populates="ticket", order_by="Assignment.assigned_at"
    )
    escalations: Mapped[List["Escalation"]] = relationship(back_populates="ticket")
    sla = relationship("SLA", back_populates="ticket", uselist=False)


class Message(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("ticket_id", "sequence_number", name="uq_message_sequence"),
        CheckConstraint(sql_in("sender_type", MESSAGE_SENDER_TYPES), name="sender_type_valid"),
        CheckConstraint(sql_in("message_type", MESSAGE_TYPES), name="message_type_valid"),
        CheckConstraint("sequence_number >= 1", name="sequence_positive"),
    )

    message_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("tickets.ticket_id"), index=True, nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sender_user_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("user_accounts.user_id")
    )
    sender_type: Mapped[str] = mapped_column(String(20), nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), default="PUBLIC", nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    ticket: Mapped[Ticket] = relationship(back_populates="messages")


class TicketEvent(CreatedAtMixin, Base):
    """Append-only ticket history."""

    __tablename__ = "ticket_events"
    __table_args__ = (CheckConstraint(sql_in("event_type", TICKET_EVENT_TYPES), name="event_type_valid"),)

    event_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("tickets.ticket_id"), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(30))
    to_status: Mapped[Optional[str]] = mapped_column(String(30))
    actor_user_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("user_accounts.user_id")
    )
    details: Mapped[Optional[dict]] = mapped_column(JSON)

    ticket: Mapped[Ticket] = relationship(back_populates="events")


class Assignment(CreatedAtMixin, Base):
    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint(sql_in("assignment_type", ASSIGNMENT_TYPES), name="assignment_type_valid"),
        CheckConstraint(
            "unassigned_at IS NULL OR unassigned_at >= assigned_at", name="unassigned_after_assigned"
        ),
    )

    assignment_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("tickets.ticket_id"), index=True, nullable=False
    )
    team_id: Mapped[str] = mapped_column(String(50), ForeignKey("teams.team_id"), nullable=False)
    assigned_user_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("user_accounts.user_id")
    )
    assigned_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("user_accounts.user_id"))
    assignment_type: Mapped[str] = mapped_column(String(20), default="AUTO", nullable=False)
    routing_reason: Mapped[str] = mapped_column(Text, nullable=False)
    rule_reference: Mapped[Optional[str]] = mapped_column(String(50))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    unassigned_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())

    ticket: Mapped[Ticket] = relationship(back_populates="assignments")
    team = relationship("Team", foreign_keys=[team_id])


class Escalation(TimestampMixin, Base):
    __tablename__ = "escalations"
    __table_args__ = (
        CheckConstraint(sql_in("escalation_level", ESCALATION_LEVELS), name="level_valid"),
        CheckConstraint(sql_in("reason_code", ESCALATION_REASONS), name="reason_code_valid"),
        CheckConstraint(sql_in("status", ESCALATION_STATUSES), name="status_valid"),
        CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= escalated_at", name="resolved_after_escalated"
        ),
    )

    escalation_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("tickets.ticket_id"), index=True, nullable=False
    )
    from_team_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("teams.team_id"))
    to_team_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("teams.team_id"))
    escalation_level: Mapped[str] = mapped_column(String(2), default="L2", nullable=False)
    reason_code: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    escalated_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("user_accounts.user_id"))
    escalated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())

    ticket: Mapped[Ticket] = relationship(back_populates="escalations")
