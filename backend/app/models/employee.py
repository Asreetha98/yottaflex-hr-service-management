"""Organisation: Department, Team, Employee."""

from datetime import date
from typing import List, Optional

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import (
    EMPLOYMENT_STATUSES,
    EMPLOYMENT_TYPES,
    SUPPORT_LEVELS,
    TEAM_TYPES,
    sql_in,
)
from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class Department(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "departments"

    department_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    teams: Mapped[List["Team"]] = relationship(back_populates="department")


class Team(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (
        CheckConstraint(sql_in("team_type", TEAM_TYPES), name="team_type_valid"),
        CheckConstraint(sql_in("support_level", SUPPORT_LEVELS), name="support_level_valid"),
    )

    team_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    department_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("departments.department_id"), index=True, nullable=False
    )
    team_type: Mapped[str] = mapped_column(String(30), nullable=False)
    support_level: Mapped[str] = mapped_column(String(2), default="L1", nullable=False)
    is_restricted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    department: Mapped[Department] = relationship(back_populates="teams")


class Employee(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint(sql_in("employment_type", EMPLOYMENT_TYPES), name="employment_type_valid"),
        CheckConstraint(
            sql_in("employment_status", EMPLOYMENT_STATUSES), name="employment_status_valid"
        ),
        CheckConstraint(
            "termination_date IS NULL OR termination_date >= hire_date", name="termination_after_hire"
        ),
        CheckConstraint("manager_id IS NULL OR manager_id <> employee_id", name="not_own_manager"),
    )

    employee_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    department_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("departments.department_id"), index=True, nullable=False
    )
    team_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("teams.team_id"))
    manager_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("employees.employee_id"), index=True
    )
    job_title: Mapped[Optional[str]] = mapped_column(String(150))
    employment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    employment_status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    location: Mapped[str] = mapped_column(String(50), nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[Optional[date]] = mapped_column(Date)

    department: Mapped[Department] = relationship()
    team: Mapped[Optional[Team]] = relationship()
    manager = relationship("Employee", remote_side=[employee_id])
    user_account = relationship(
        "UserAccount", back_populates="employee", uselist=False, foreign_keys="UserAccount.employee_id"
    )

    @property
    def full_name(self) -> str:
        return "%s %s" % (self.first_name, self.last_name)
