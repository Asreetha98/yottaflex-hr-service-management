from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.constants import EMPLOYMENT_STATUSES, EMPLOYMENT_TYPES
from app.schemas import ORMModel


class DepartmentOut(ORMModel):
    department_id: str
    code: str
    name: str
    description: Optional[str] = None
    is_active: bool = True


class TeamOut(ORMModel):
    team_id: str
    name: str
    department_id: str
    team_type: str
    support_level: str
    is_restricted: bool
    is_active: bool = True


class EmployeeCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    department_id: str
    team_id: Optional[str] = None
    manager_id: Optional[str] = None
    job_title: Optional[str] = Field(default=None, max_length=150)
    employment_type: str = "FULL_TIME"
    location: str = Field(min_length=1, max_length=50)
    hire_date: date

    @field_validator("employment_type")
    @classmethod
    def _valid_type(cls, value: str) -> str:
        if value not in EMPLOYMENT_TYPES:
            raise ValueError("employment_type must be one of %s" % ", ".join(EMPLOYMENT_TYPES))
        return value


class EmployeeOut(ORMModel):
    employee_id: str
    first_name: str
    last_name: str
    email: str
    department_id: str
    team_id: Optional[str] = None
    manager_id: Optional[str] = None
    job_title: Optional[str] = None
    employment_type: str
    employment_status: str
    location: str
    hire_date: date
    termination_date: Optional[date] = None
