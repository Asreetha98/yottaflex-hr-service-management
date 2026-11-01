"""Declarative base, shared mixins and a UTC-safe datetime type."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    """Timezone-aware current time in UTC (all timestamps in the system are UTC)."""
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """DateTime(timezone=True) that always returns tz-aware UTC values.

    SQLite drops tzinfo; this decorator re-attaches UTC so engines can compare
    datetimes safely on every backend.
    """

    impl = DateTime
    cache_ok = True

    def __init__(self) -> None:
        super().__init__(timezone=True)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class CreatedAtMixin:
    """Append-only entities: creation time only."""

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class TimestampMixin(CreatedAtMixin):
    """created_at + updated_at (both UTC)."""

    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )


class SoftDeleteMixin:
    """Logical deletion: rows are hidden, never removed."""

    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True, server_default="0"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True)

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = utcnow()
