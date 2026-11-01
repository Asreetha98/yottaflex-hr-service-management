"""SLA: BusinessCalendar, HolidayCalendar, SLA, SLAPauseEvent."""

from datetime import date, datetime, time
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import PRIORITIES, SLA_PAUSE_REASONS, SLA_POLICIES, SLA_STATUSES, sql_in
from app.models.base import Base, CreatedAtMixin, SoftDeleteMixin, TimestampMixin, UTCDateTime


class BusinessCalendar(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "business_calendars"
    __table_args__ = (CheckConstraint("end_time > start_time", name="hours_ordered"),)

    calendar_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    work_days: Mapped[list] = mapped_column(JSON, default=lambda: [0, 1, 2, 3, 4], nullable=False)
    start_time: Mapped[time] = mapped_column(Time, default=time(9, 0), nullable=False)
    end_time: Mapped[time] = mapped_column(Time, default=time(17, 0), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    holidays: Mapped[List["HolidayCalendar"]] = relationship(back_populates="calendar")


class HolidayCalendar(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "holiday_calendars"
    __table_args__ = (UniqueConstraint("calendar_id", "holiday_date", name="uq_holiday_per_calendar"),)

    holiday_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    calendar_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("business_calendars.calendar_id"), index=True, nullable=False
    )
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)

    calendar: Mapped[BusinessCalendar] = relationship(back_populates="holidays")


class SLA(TimestampMixin, Base):
    __tablename__ = "slas"
    __table_args__ = (
        CheckConstraint(sql_in("sla_policy", SLA_POLICIES), name="sla_policy_valid"),
        CheckConstraint(sql_in("priority", PRIORITIES), name="priority_valid"),
        CheckConstraint(sql_in("status", SLA_STATUSES), name="status_valid"),
        CheckConstraint("target_hours > 0", name="target_positive"),
        CheckConstraint("total_paused_business_minutes >= 0", name="paused_non_negative"),
        CheckConstraint("due_at >= started_at", name="due_after_start"),
    )

    sla_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("tickets.ticket_id"), unique=True, nullable=False
    )
    calendar_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("business_calendars.calendar_id"), nullable=False
    )
    sla_policy: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[str] = mapped_column(String(2), nullable=False)
    target_hours: Mapped[float] = mapped_column(Float, nullable=False)
    first_response_target_hours: Mapped[Optional[float]] = mapped_column(Float)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    due_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    first_response_due_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    first_response_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    total_paused_business_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True, nullable=False)
    is_breached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    breached_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())

    ticket = relationship("Ticket", back_populates="sla")
    calendar: Mapped[BusinessCalendar] = relationship()
    pauses: Mapped[List["SLAPauseEvent"]] = relationship(
        back_populates="sla", order_by="SLAPauseEvent.paused_at"
    )


class SLAPauseEvent(CreatedAtMixin, Base):
    __tablename__ = "sla_pause_events"
    __table_args__ = (
        CheckConstraint(sql_in("reason", SLA_PAUSE_REASONS), name="reason_valid"),
        CheckConstraint("resumed_at IS NULL OR resumed_at >= paused_at", name="resumed_after_paused"),
        CheckConstraint(
            "business_minutes_paused IS NULL OR business_minutes_paused >= 0", name="minutes_non_negative"
        ),
    )

    pause_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    sla_id: Mapped[str] = mapped_column(String(50), ForeignKey("slas.sla_id"), index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    paused_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    resumed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    business_minutes_paused: Mapped[Optional[int]] = mapped_column(Integer)
    paused_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("user_accounts.user_id"))

    sla: Mapped[SLA] = relationship(back_populates="pauses")
