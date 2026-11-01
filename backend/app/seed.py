"""Idempotent bootstrap of reference data and (optionally) demo users.

Safe to run on every start-up: each block checks for existing rows first.
"""

from datetime import date, time
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import CATEGORY_CODES, ROLE_NAMES
from app.models.base import utcnow
from app.models.employee import Department, Employee, Team
from app.models.knowledge import Category
from app.models.rules import CategoryRule, ClarificationTemplate as ClarificationTemplateRow, RoutingRule
from app.models.sla import BusinessCalendar, HolidayCalendar
from app.models.user import Permission, Role, UserAccount
from app.rules.clarification_engine import DEFAULT_TEMPLATES
from app.rules.classification_engine import DEFAULT_RULES
from app.rules.routing_engine import DEFAULT_ROUTING_RULES
from app.security.password import hash_password
from app.security.permissions import ALL_PERMISSIONS, PERMISSION_DESCRIPTIONS, ROLE_PERMISSIONS

DEPARTMENTS: Tuple[Tuple[str, str, str, str], ...] = (
    ("DEPT-01", "HR", "Human Resources", "People operations, payroll, benefits and employee relations"),
    ("DEPT-02", "IT", "Information Technology", "IT operations and support"),
    ("DEPT-03", "ENG", "Engineering", "Product engineering"),
    ("DEPT-04", "FIN", "Finance", "Finance and accounting"),
)

# (team_id, name, department, team_type, support_level, restricted)
TEAMS: Tuple[Tuple[str, str, str, str, str, bool], ...] = (
    ("TEAM-01", "HR General Support", "DEPT-01", "HR_GENERAL", "L1", False),
    ("TEAM-02", "Payroll Team", "DEPT-01", "PAYROLL", "L1", False),
    ("TEAM-03", "Leave Management Team", "DEPT-01", "LEAVE", "L1", False),
    ("TEAM-04", "Benefits Team", "DEPT-01", "BENEFITS", "L1", False),
    ("TEAM-05", "Onboarding Team", "DEPT-01", "ONBOARDING", "L1", False),
    ("TEAM-06", "Employee Relations (L2)", "DEPT-01", "EMPLOYEE_RELATIONS", "L2", True),
    ("TEAM-07", "HR Operations (L2)", "DEPT-01", "HR_GENERAL", "L2", False),
    ("TEAM-08", "IT Operations", "DEPT-02", "IT_OPS", "L1", False),
)

CATEGORIES: Tuple[Tuple[str, str, str], ...] = (
    ("CAT-01", "PAYROLL", "Payroll"),
    ("CAT-02", "LEAVE", "Leave"),
    ("CAT-03", "BENEFITS", "Benefits"),
    ("CAT-04", "ONBOARDING", "Onboarding"),
    ("CAT-05", "IT", "IT Support"),
    ("CAT-06", "GENERAL", "General"),
)

HOLIDAYS: Tuple[Tuple[date, str], ...] = (
    (date(2026, 1, 1), "New Year's Day"),
    (date(2026, 5, 25), "Memorial Day"),
    (date(2026, 7, 3), "Independence Day (observed)"),
    (date(2026, 9, 7), "Labor Day"),
    (date(2026, 11, 26), "Thanksgiving"),
    (date(2026, 12, 25), "Christmas Day"),
)

# username, role, first, last, employee_id, dept, team, manager, title, can_view_sensitive
DEMO_USERS: Tuple[Tuple[str, str, str, str, str, str, Optional[str], Optional[str], str, bool], ...] = (
    ("admin", "ADMIN", "Alex", "Admin", "EMP-000001", "DEPT-01", "TEAM-01", None, "HR Systems Administrator", True),
    ("hr_partner", "HR_PARTNER", "Hannah", "Partner", "EMP-000002", "DEPT-01", "TEAM-02", "EMP-000001", "HR Business Partner", False),
    ("hr_sensitive", "HR_PARTNER", "Sam", "Relations", "EMP-000003", "DEPT-01", "TEAM-06", "EMP-000001", "Employee Relations Partner", True),
    ("it_ops", "IT_OPS", "Ian", "Ops", "EMP-000004", "DEPT-02", "TEAM-08", "EMP-000001", "IT Operations Analyst", False),
    ("manager", "MANAGER", "Maya", "Manager", "EMP-000005", "DEPT-03", None, "EMP-000001", "Engineering Manager", False),
    ("employee", "EMPLOYEE", "Eli", "Employee", "EMP-000006", "DEPT-03", None, "EMP-000005", "Software Engineer", False),
    ("employee2", "EMPLOYEE", "Eva", "Employee", "EMP-000007", "DEPT-04", None, "EMP-000001", "Financial Analyst", False),
)


def seed_permissions_and_roles(db: Session) -> None:
    perms: Dict[str, Permission] = {p.code: p for p in db.query(Permission).all()}
    for code in sorted(ALL_PERMISSIONS):
        if code not in perms:
            perm = Permission(permission_id="PERM-%s" % code.upper(), code=code,
                              description=PERMISSION_DESCRIPTIONS.get(code))
            db.add(perm)
            perms[code] = perm
    db.flush()
    roles: Dict[str, Role] = {r.name: r for r in db.query(Role).all()}
    for name in ROLE_NAMES:
        role = roles.get(name)
        if role is None:
            role = Role(role_id="ROLE-%s" % name, name=name, description="%s role" % name.replace("_", " ").title())
            db.add(role)
            roles[name] = role
            db.flush()
        wanted = {perms[c] for c in ROLE_PERMISSIONS[name]}
        if set(role.permissions) != wanted:
            role.permissions = sorted(wanted, key=lambda p: p.code)
    db.flush()


def seed_organisation(db: Session) -> None:
    for dept_id, code, name, desc in DEPARTMENTS:
        if not db.get(Department, dept_id):
            db.add(Department(department_id=dept_id, code=code, name=name, description=desc))
    db.flush()
    for team_id, name, dept, team_type, level, restricted in TEAMS:
        if not db.get(Team, team_id):
            db.add(Team(team_id=team_id, name=name, department_id=dept, team_type=team_type,
                        support_level=level, is_restricted=restricted))
    db.flush()


def seed_categories(db: Session) -> None:
    assert {c[1] for c in CATEGORIES} == set(CATEGORY_CODES)
    for cat_id, code, name in CATEGORIES:
        if not db.get(Category, cat_id):
            db.add(Category(category_id=cat_id, code=code, name=name))
    db.flush()


def seed_calendar(db: Session) -> None:
    if db.get(BusinessCalendar, "CAL-01") is None:
        db.add(BusinessCalendar(calendar_id="CAL-01", name="Default UTC business calendar", timezone="UTC",
                                work_days=[0, 1, 2, 3, 4], start_time=time(9, 0), end_time=time(17, 0),
                                is_default=True))
        db.flush()
    existing = {h.holiday_date for h in db.query(HolidayCalendar).filter(HolidayCalendar.calendar_id == "CAL-01")}
    number = db.query(HolidayCalendar).count()
    for day, name in HOLIDAYS:
        if day not in existing:
            number += 1
            db.add(HolidayCalendar(holiday_id="HOL-%06d" % number, calendar_id="CAL-01",
                                   holiday_date=day, name=name))
    db.flush()


def seed_rules(db: Session) -> None:
    categories = {c.code: c.category_id for c in db.query(Category).all()}
    if db.query(CategoryRule).count() == 0:
        number = 0
        for rule in DEFAULT_RULES:
            for term, rule_type, weight in rule.iter_terms():
                number += 1
                db.add(CategoryRule(rule_id="CRL-%06d" % number, category_id=categories[rule.category],
                                    rule_type=rule_type, term=term, weight=weight))
        db.flush()

    if db.query(RoutingRule).count() == 0:
        teams_by_key = {(t.team_type, t.support_level): t.team_id for t in db.query(Team).all()}
        for rule in DEFAULT_ROUTING_RULES:
            db.add(RoutingRule(
                rule_id=rule.rule_id, name=rule.name,
                category_id=categories.get(rule.category) if rule.category else None,
                is_sensitive=rule.is_sensitive, priority_order=rule.priority_order,
                target_team_id=teams_by_key[(rule.target_team, rule.support_level)],
                description=rule.name,
            ))
        db.flush()

    if db.query(ClarificationTemplateRow).count() == 0:
        for index, tpl in enumerate(DEFAULT_TEMPLATES, start=1):
            db.add(ClarificationTemplateRow(
                template_id="CLT-%02d" % index, category_id=categories[tpl.category],
                required_field=tpl.required_field, question_text=tpl.question_text,
                detection_keywords=list(tpl.detection_keywords), display_order=tpl.display_order,
            ))
        db.flush()


def seed_demo_users(db: Session, password: Optional[str] = None) -> None:
    password = password or get_settings().demo_user_password
    roles = {r.name: r for r in db.query(Role).all()}
    created_hash: Optional[str] = None
    # Employees first (managers referenced by FK), in id order.
    for row in sorted(DEMO_USERS, key=lambda r: r[4]):
        username, role, first, last, emp_id, dept, team, manager, title, _sensitive = row
        if not db.get(Employee, emp_id):
            db.add(Employee(
                employee_id=emp_id, first_name=first, last_name=last, email="%s@yottaflex.example" % username,
                department_id=dept, team_id=team, manager_id=None, job_title=title,
                employment_type="FULL_TIME", employment_status="ACTIVE", location="US",
                hire_date=date(2024, 1, 15),
            ))
    db.flush()
    for row in DEMO_USERS:
        emp = db.get(Employee, row[4])
        if emp is not None and emp.manager_id is None and row[7]:
            emp.manager_id = row[7]
    db.flush()
    number = db.query(UserAccount).count()
    for username, role, first, last, emp_id, dept, team, manager, title, sensitive in DEMO_USERS:
        if db.query(UserAccount).filter(UserAccount.username == username).first():
            continue
        number += 1
        created_hash = created_hash or hash_password(password)
        user = UserAccount(
            user_id="USR-%06d" % number, employee_id=emp_id, username=username,
            email="%s@yottaflex.example" % username, password_hash=created_hash,
            can_view_sensitive=sensitive, last_login_at=None,
        )
        user.roles = [roles[role]]
        db.add(user)
    db.flush()


def seed_all(db: Session, include_demo_users: bool = True) -> None:
    seed_permissions_and_roles(db)
    seed_organisation(db)
    seed_categories(db)
    seed_calendar(db)
    seed_rules(db)
    if include_demo_users:
        seed_demo_users(db)
    db.commit()
