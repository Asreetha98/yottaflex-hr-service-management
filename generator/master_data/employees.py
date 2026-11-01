"""Employees, user accounts and role assignments."""

import random
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from generator.config import MASTER_CREATED_AT, REFERENCE_DATE, USE_FAKER, stage_rng
from generator.master_data.departments import sd, ts
from generator.utils.dataset import Dataset
from generator.utils.faker_config import get_name_source
from generator.utils.id_generator import employee_id, user_id

# A bcrypt-shaped placeholder: generated accounts exist for data realism and cannot log in.
PLACEHOLDER_PASSWORD_HASH = "$2b$12$" + "x" * 53

# username, role, first, last, dept, team, manager emp no, title, can_view_sensitive
DEMO = (
    ("admin", "ADMIN", "Alex", "Admin", "DEPT-01", "TEAM-01", None, "HR Systems Administrator", True),
    ("hr_partner", "HR_PARTNER", "Hannah", "Partner", "DEPT-01", "TEAM-02", 1, "HR Business Partner", False),
    ("hr_sensitive", "HR_PARTNER", "Sam", "Relations", "DEPT-01", "TEAM-06", 1, "Employee Relations Partner", True),
    ("it_ops", "IT_OPS", "Ian", "Ops", "DEPT-02", "TEAM-08", 1, "IT Operations Analyst", False),
    ("manager", "MANAGER", "Maya", "Manager", "DEPT-03", None, 1, "Engineering Manager", False),
    ("employee", "EMPLOYEE", "Eli", "Employee", "DEPT-03", None, 5, "Software Engineer", False),
    ("employee2", "EMPLOYEE", "Eva", "Employee", "DEPT-04", None, 1, "Financial Analyst", False),
)

HR_TEAM_CYCLE = ("TEAM-02", "TEAM-03", "TEAM-04", "TEAM-05", "TEAM-06", "TEAM-01", "TEAM-07")
HR_TITLES = {
    "TEAM-01": "HR Generalist", "TEAM-02": "Payroll Specialist", "TEAM-03": "Leave Administrator",
    "TEAM-04": "Benefits Specialist", "TEAM-05": "Onboarding Coordinator",
    "TEAM-06": "Employee Relations Partner", "TEAM-07": "HR Operations Lead",
}
LOCATIONS = (("US", 50), ("UK", 20), ("IN", 20), ("DE", 10))
EMPLOYMENT_TYPES = (("FULL_TIME", 80), ("PART_TIME", 8), ("CONTRACTOR", 8), ("INTERN", 4))


def _weighted(rng: random.Random, options: Any) -> str:
    total = sum(w for _, w in options)
    pick = rng.uniform(0, total)
    running = 0.0
    for value, weight in options:
        running += weight
        if pick <= running:
            return value
    return options[-1][0]


def _random_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def generate_employees(ds: Dataset) -> None:
    rng = stage_rng("employees")
    names = get_name_source(rng, USE_FAKER)
    total = ds.size.employees
    if total < 30:
        raise ValueError("employees must be >= 30")
    hr_count = max(7, int(round(total * 0.08)))
    it_count = max(2, int(round(total * 0.04)))
    hr_end = 7 + hr_count
    it_end = hr_end + it_count

    plans: List[Dict[str, Any]] = []
    for number, (username, role, first, last, dept, team, manager, title, sensitive) in enumerate(DEMO, start=1):
        plans.append(dict(number=number, username=username, role=role, first=first, last=last, dept=dept,
                          team=team, manager=manager, title=title, sensitive=sensitive,
                          etype="FULL_TIME", location="US", hire=date(2024, 1, 15), status="ACTIVE"))

    managers_by_dept: Dict[str, List[int]] = {"DEPT-03": [5], "DEPT-04": [1]}
    for number in range(8, total + 1):
        first, last = names.first_name(), names.last_name()
        username = ("%s.%s.%d" % (first, last, number)).lower()
        common = dict(number=number, username=username, first=first, last=last, sensitive=False,
                      etype=_weighted(rng, EMPLOYMENT_TYPES), location=_weighted(rng, LOCATIONS))
        if number <= hr_end:
            team = HR_TEAM_CYCLE[(number - 8) % len(HR_TEAM_CYCLE)]
            plans.append(dict(common, role="HR_PARTNER", dept="DEPT-01", team=team, manager=1,
                              title=HR_TITLES[team], sensitive=(team == "TEAM-06"), etype="FULL_TIME",
                              hire=_random_date(rng, date(2019, 1, 1), date(2024, 12, 31)), status="ACTIVE"))
        elif number <= it_end:
            plans.append(dict(common, role="IT_OPS", dept="DEPT-02", team="TEAM-08", manager=4,
                              title="IT Support Engineer", etype="FULL_TIME",
                              hire=_random_date(rng, date(2019, 1, 1), date(2025, 12, 31)), status="ACTIVE"))
        else:
            dept = "DEPT-03" if rng.random() < 0.65 else "DEPT-04"
            is_manager = (number - it_end) % 12 == 0
            if rng.random() < 0.12:
                hire = _random_date(rng, date(2026, 8, 1), date(2026, 10, 15))
            else:
                hire = _random_date(rng, date(2018, 1, 1), date(2026, 7, 31))
            status = "ACTIVE"
            roll = rng.random()
            if roll < 0.03 and hire < date(2026, 6, 1):
                status = "TERMINATED"
            elif roll < 0.05:
                status = "ON_LEAVE"
            if is_manager:
                manager = 1
                managers_by_dept[dept].append(number)
                role, title = "MANAGER", "Team Manager"
            else:
                manager = rng.choice(managers_by_dept[dept])
                role, title = "EMPLOYEE", "Software Engineer" if dept == "DEPT-03" else "Financial Analyst"
            plans.append(dict(common, role=role, dept=dept, team=None, manager=manager, title=title,
                              hire=hire, status=status))

    staff: List[Dict[str, Any]] = []
    ctx: Dict[str, Dict[str, Any]] = {}
    for p in plans:
        emp = employee_id(p["number"])
        is_demo = p["number"] <= len(DEMO)
        email = "%s@yottaflex.example" % p["username"] if is_demo else "%s@yottaflex.example" % p["username"]
        termination: Optional[date] = None
        if p["status"] == "TERMINATED":
            latest = date(2026, 9, 30)
            span = max(0, (latest - p["hire"]).days)
            termination = p["hire"] + timedelta(days=min(span, 90 + rng.randint(0, 400)))
        ds.add("employees", employee_id=emp, first_name=p["first"], last_name=p["last"], email=email,
               department_id=p["dept"], team_id=p["team"],
               manager_id=employee_id(p["manager"]) if p["manager"] else None,
               job_title=p["title"], employment_type=p["etype"], employment_status=p["status"],
               location=p["location"], hire_date=p["hire"], termination_date=termination, **ts(), **sd())
        usr = user_id(p["number"])
        last_login = None if p["status"] == "TERMINATED" else MASTER_CREATED_AT
        ds.add("user_accounts", user_id=usr, employee_id=emp, username=p["username"], email=email,
               password_hash=PLACEHOLDER_PASSWORD_HASH, is_active=p["status"] != "TERMINATED",
               can_view_sensitive=p["sensitive"], last_login_at=last_login, **ts(), **sd())
        ds.add("user_roles", user_id=usr, role_id="ROLE-%s" % p["role"], assigned_at=MASTER_CREATED_AT,
               assigned_by=user_id(1) if p["number"] > 1 else None)
        staff.append(dict(user_id=usr, employee_id=emp, role=p["role"], team_id=p["team"],
                          can_view_sensitive=p["sensitive"], active=p["status"] != "TERMINATED"))
        ctx[emp] = dict(department_id=p["dept"], employment_type=p["etype"], location=p["location"],
                        status=p["status"], hire_date=p["hire"], user_id=usr, role=p["role"])
    ds.extra["staff"] = staff
    ds.extra["employee_ctx"] = ctx
    ds.extra["reference_date"] = REFERENCE_DATE
