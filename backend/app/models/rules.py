"""Configurable rules stored as data: CategoryRule, RoutingRule, ClarificationTemplate."""

from typing import Optional

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

from app.constants import RULE_TYPES, sql_in
from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class CategoryRule(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "category_rules"
    __table_args__ = (
        CheckConstraint(sql_in("rule_type", RULE_TYPES), name="rule_type_valid"),
        CheckConstraint("weight > 0", name="weight_positive"),
    )

    rule_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    category_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("categories.category_id"), index=True, nullable=False
    )
    rule_type: Mapped[str] = mapped_column(String(20), nullable=False)
    term: Mapped[str] = mapped_column(String(255), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    category = relationship("Category")


class RoutingRule(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "routing_rules"
    __table_args__ = (CheckConstraint("priority_order >= 1", name="priority_order_positive"),)

    rule_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("categories.category_id"))
    is_sensitive: Mapped[Optional[bool]] = mapped_column(Boolean)
    priority_order: Mapped[int] = mapped_column(Integer, nullable=False)
    target_team_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("teams.team_id"), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    category = relationship("Category")
    target_team = relationship("Team")


class ClarificationTemplate(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "clarification_templates"
    __table_args__ = (
        UniqueConstraint("category_id", "required_field", name="uq_clarification_field"),
    )

    template_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    category_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("categories.category_id"), index=True, nullable=False
    )
    required_field: Mapped[str] = mapped_column(String(50), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    detection_keywords: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    category = relationship("Category")
