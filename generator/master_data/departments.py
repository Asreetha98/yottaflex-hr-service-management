"""Departments, teams, business calendar, holidays, roles and permissions."""

from datetime import date, time
from typing import Any, Dict

from generator.config import MASTER_CREATED_AT
from generator.utils.dataset import Dataset
from app.constants import ROLE_NAMES
from app.security.permissions import ALL_PERMISSIONS, PERMISSION_DESCRIPTIONS, ROLE_PERMISSIONS

DEPARTMENTS = (
    ("DEPT-01", "HR", "Human Resources", "People operations, payroll, benefits and employee relations"),
    ("DEPT-02", "IT", "Information Technology", "IT operations and support"),
    ("DEPT-03", "ENG", "Engineering", "Product engineering"),
    ("DEPT-04", "FIN", "Finance", "Finance and accounting"),
)

# (team_id, name, department, team_type, support_level, restricted)
TEAMS = (
    ("TEAM-01", "HR General Support", "DEPT-01", "HR_GENERAL", "L1", False),
    ("TEAM-02", "Payroll Team", "DEPT-01", "PAYROLL", "L1", False),
    ("TEAM-03", "Leave Management Team", "DEPT-01", "LEAVE", "L1", False),
    ("TEAM-04", "Benefits Team", "DEPT-01", "BENEFITS", "L1", False),
    ("TEAM-05", "Onboarding Team", "DEPT-01", "ONBOARDING", "L1", False),
    ("TEAM-06", "Employee Relations (L2)", "DEPT-01", "EMPLOYEE_RELATIONS", "L2", True),
    ("TEAM-07", "HR Operations (L2)", "DEPT-01", "HR_GENERAL", "L2", False),
    ("TEAM-08", "IT Operations", "DEPT-02", "IT_OPS", "L1", False),
)

HOLIDAYS = (
    (date(2026, 1, 1), "New Year's Day"),
    (date(2026, 5, 25), "Memorial Day"),
    (date(2026, 7, 3), "Independence Day (observed)"),
    (date(2026, 9, 7), "Labor Day"),
    (date(2026, 11, 26), "Thanksgiving"),
    (date(2026, 12, 25), "Christmas Day"),
)

CALENDAR_ID = "CAL-01"


def ts() -> Dict[str, Any]:
    return {"created_at": MASTER_CREATED_AT, "updated_at": MASTER_CREATED_AT}


def sd() -> Dict[str, Any]:
    return {"is_deleted": False, "deleted_at": None}


def generate_departments(ds: Dataset) -> None:
    for dept_id, code, name, desc in DEPARTMENTS:
        ds.add("departments", department_id=dept_id, code=code, name=name, description=desc,
               is_active=True, **ts(), **sd())


def generate_teams(ds: Dataset) -> None:
    for team_id, name, dept, team_type, level, restricted in TEAMS:
        ds.add("teams", team_id=team_id, name=name, department_id=dept, team_type=team_type,
               support_level=level, is_restricted=restricted, is_active=True, **ts(), **sd())


def generate_calendar(ds: Dataset) -> None:
    ds.add("business_calendars", calendar_id=CALENDAR_ID, name="Default UTC business calendar", timezone="UTC",
           work_days=[0, 1, 2, 3, 4], start_time=time(9, 0), end_time=time(17, 0), is_default=True,
           **ts(), **sd())
    for number, (day, name) in enumerate(HOLIDAYS, start=1):
        ds.add("holiday_calendars", holiday_id="HOL-%06d" % number, calendar_id=CALENDAR_ID,
               holiday_date=day, name=name, **ts(), **sd())


def generate_roles(ds: Dataset) -> None:
    for name in ROLE_NAMES:
        ds.add("roles", role_id="ROLE-%s" % name, name=name,
               description="%s role" % name.replace("_", " ").title(), **ts())
    for code in sorted(ALL_PERMISSIONS):
        ds.add("permissions", permission_id="PERM-%s" % code.upper(), code=code,
               description=PERMISSION_DESCRIPTIONS.get(code), **ts())
    for role in ROLE_NAMES:
        for code in sorted(ROLE_PERMISSIONS[role]):
            ds.add("role_permissions", role_id="ROLE-%s" % role, permission_id="PERM-%s" % code.upper())


def generate_organisation(ds: Dataset) -> None:
    generate_departments(ds)
    generate_teams(ds)
    generate_calendar(ds)
    generate_roles(ds)
