"""Resolution of a ticket (one ticket can have several across reopen cycles)."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import RESOLUTION_TYPES, sql_in
from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UTCDateTime


class Resolution(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "resolutions"
    __table_args__ = (
        CheckConstraint(sql_in("resolution_type", RESOLUTION_TYPES), name="resolution_type_valid"),
        CheckConstraint(
            "satisfaction_score IS NULL OR (satisfaction_score >= 1 AND satisfaction_score <= 5)",
            name="satisfaction_range",
        ),
    )

    resolution_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("tickets.ticket_id"), index=True, nullable=False
    )
    resolution_type: Mapped[str] = mapped_column(String(30), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    resolution_text: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("policy_versions.version_id")
    )
    citation_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("policy_citations.citation_id")
    )
    article_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("knowledge_articles.article_id")
    )
    resolved_by: Mapped[str] = mapped_column(
        String(50), ForeignKey("user_accounts.user_id"), nullable=False
    )
    resolved_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    satisfaction_score: Mapped[Optional[int]] = mapped_column(Integer)
    was_reopened: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    ticket = relationship("Ticket")
