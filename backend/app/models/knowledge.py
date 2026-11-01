"""Knowledge base: Category, KnowledgeArticle and the article_categories bridge."""

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import ARTICLE_STATUSES, CATEGORY_CODES, sql_in
from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UTCDateTime

article_categories = Table(
    "article_categories",
    Base.metadata,
    Column("article_id", String(50), ForeignKey("knowledge_articles.article_id"), primary_key=True),
    Column("category_id", String(50), ForeignKey("categories.category_id"), primary_key=True),
)


class Category(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (CheckConstraint(sql_in("code", CATEGORY_CODES), name="code_valid"),)

    category_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class KnowledgeArticle(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "knowledge_articles"
    __table_args__ = (
        CheckConstraint(sql_in("status", ARTICLE_STATUSES), name="status_valid"),
        CheckConstraint("view_count >= 0", name="view_count_non_negative"),
    )

    article_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    primary_category_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("categories.category_id"), index=True, nullable=False
    )
    policy_version_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("policy_versions.version_id")
    )
    keywords: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    audience: Mapped[list] = mapped_column(JSON, default=lambda: ["ALL"], nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    last_reviewed_at: Mapped[Optional[date]] = mapped_column(Date)
    author_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("user_accounts.user_id"))

    primary_category: Mapped[Category] = relationship(foreign_keys=[primary_category_id])
    categories: Mapped[List[Category]] = relationship(secondary=article_categories)
    policy_version = relationship("PolicyVersion", foreign_keys=[policy_version_id])

    @property
    def category_code(self) -> Optional[str]:
        return self.primary_category.code if self.primary_category is not None else None
