"""Policy management: PolicyDocument, PolicyVersion, PolicyAudience, PolicyCitation."""

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import AUDIENCE_TYPES, POLICY_STATUSES, VERSION_STATUSES, sql_in
from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UTCDateTime


class PolicyDocument(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "policy_documents"
    __table_args__ = (CheckConstraint(sql_in("status", POLICY_STATUSES), name="status_valid"),)

    policy_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("categories.category_id"))
    owner_department_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("departments.department_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)

    versions: Mapped[List["PolicyVersion"]] = relationship(
        back_populates="policy", order_by="PolicyVersion.version_number"
    )


class PolicyVersion(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint("policy_id", "version_number", name="uq_policy_version_number"),
        CheckConstraint(sql_in("status", VERSION_STATUSES), name="status_valid"),
        CheckConstraint("version_number >= 1", name="version_number_positive"),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="effective_window_ordered",
        ),
    )

    version_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    policy_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("policy_documents.policy_id"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    effective_from: Mapped[Optional[date]] = mapped_column(Date)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    published_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    published_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("user_accounts.user_id"))
    created_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("user_accounts.user_id"))
    supersedes_version_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("policy_versions.version_id")
    )

    policy: Mapped[PolicyDocument] = relationship(back_populates="versions")
    audiences: Mapped[List["PolicyAudience"]] = relationship(
        back_populates="version", lazy="selectin"
    )
    citations: Mapped[List["PolicyCitation"]] = relationship(back_populates="version")


class PolicyAudience(TimestampMixin, Base):
    __tablename__ = "policy_audiences"
    __table_args__ = (
        CheckConstraint(sql_in("audience_type", AUDIENCE_TYPES), name="audience_type_valid"),
        CheckConstraint(
            "audience_type = 'ALL' OR audience_value IS NOT NULL", name="value_required_unless_all"
        ),
    )

    audience_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    version_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("policy_versions.version_id"), index=True, nullable=False
    )
    audience_type: Mapped[str] = mapped_column(String(30), nullable=False)
    audience_value: Mapped[Optional[str]] = mapped_column(String(100))

    version: Mapped[PolicyVersion] = relationship(back_populates="audiences")


class PolicyCitation(TimestampMixin, Base):
    __tablename__ = "policy_citations"

    citation_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    version_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("policy_versions.version_id"), index=True, nullable=False
    )
    article_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("knowledge_articles.article_id")
    )
    section_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)

    version: Mapped[PolicyVersion] = relationship(back_populates="citations")
