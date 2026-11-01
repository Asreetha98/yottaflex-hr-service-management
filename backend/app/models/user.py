"""Identity and access: UserAccount, Role, Permission and the two bridge tables."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    String,
    Table,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import ROLE_NAMES, sql_in
from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UTCDateTime, utcnow

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String(50), ForeignKey("user_accounts.user_id"), primary_key=True),
    Column("role_id", String(50), ForeignKey("roles.role_id"), primary_key=True),
    Column("assigned_at", UTCDateTime(), nullable=False, default=utcnow),
    Column("assigned_by", String(50), ForeignKey("user_accounts.user_id"), nullable=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String(50), ForeignKey("roles.role_id"), primary_key=True),
    Column("permission_id", String(50), ForeignKey("permissions.permission_id"), primary_key=True),
)


class Permission(TimestampMixin, Base):
    __tablename__ = "permissions"

    permission_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))


class Role(TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (CheckConstraint(sql_in("name", ROLE_NAMES), name="name_valid"),)

    role_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))

    permissions: Mapped[List[Permission]] = relationship(secondary=role_permissions, lazy="selectin")


class UserAccount(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "user_accounts"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    employee_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("employees.employee_id"), unique=True, nullable=True
    )
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_view_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True)

    roles: Mapped[List[Role]] = relationship(
        secondary=user_roles,
        primaryjoin="UserAccount.user_id == user_roles.c.user_id",
        secondaryjoin="Role.role_id == user_roles.c.role_id",
        lazy="selectin",
    )
    employee = relationship("Employee", back_populates="user_account", foreign_keys=[employee_id])

    @property
    def role_names(self) -> List[str]:
        return [r.name for r in self.roles]
