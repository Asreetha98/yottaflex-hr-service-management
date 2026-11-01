from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_permission
from app.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.employee import Department, Employee, Team
from app.models.user import UserAccount
from app.repositories.employee_repository import EmployeeRepository
from app.schemas import Page
from app.schemas.employee import DepartmentOut, EmployeeCreate, EmployeeOut, TeamOut
from app.security.permissions import has_permission
from app.services.audit_service import AuditService
from app.services.ids import next_id

router = APIRouter(prefix="/employees", tags=["employees"])
audit = AuditService()


def _can_see_employee(db: Session, user: UserAccount, employee: Employee) -> bool:
    roles = user.role_names
    if has_permission(roles, "view_all_tickets") or has_permission(roles, "manage_users"):
        return True
    if user.employee_id == employee.employee_id:
        return True
    return has_permission(roles, "view_team_tickets") and employee.manager_id == user.employee_id


@router.get("", response_model=Page[EmployeeOut])
def list_employees(
    department_id: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: UserAccount = Depends(require_permission("view_team_tickets")),
    db: Session = Depends(get_db),
) -> Page[EmployeeOut]:
    query = db.query(Employee).filter(Employee.is_deleted.is_(False))
    roles = user.role_names
    if not (has_permission(roles, "view_all_tickets") or has_permission(roles, "manage_users")):
        query = query.filter(Employee.manager_id == user.employee_id)  # managers: direct reports only
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if search:
        like = "%%%s%%" % search.strip()
        query = query.filter(
            Employee.first_name.ilike(like) | Employee.last_name.ilike(like) | Employee.email.ilike(like)
        )
    total = query.count()
    items = query.order_by(Employee.employee_id).offset(skip).limit(limit).all()
    return Page[EmployeeOut](items=[EmployeeOut.model_validate(e) for e in items], total=total, skip=skip, limit=limit)


@router.post("", response_model=EmployeeOut, status_code=201)
def create_employee(
    body: EmployeeCreate,
    user: UserAccount = Depends(require_permission("manage_users")),
    db: Session = Depends(get_db),
) -> EmployeeOut:
    if db.query(Employee).filter(Employee.email == body.email).first():
        raise ConflictError("An employee with this email already exists", "EMAIL_EXISTS")
    if not db.query(Department).filter(Department.department_id == body.department_id).first():
        raise NotFoundError("Department %s not found" % body.department_id)
    if body.team_id and not db.query(Team).filter(Team.team_id == body.team_id).first():
        raise NotFoundError("Team %s not found" % body.team_id)
    if body.manager_id and not db.query(Employee).filter(Employee.employee_id == body.manager_id).first():
        raise NotFoundError("Manager %s not found" % body.manager_id)
    employee = Employee(
        employee_id=next_id(db, Employee.employee_id, "EMP-", 6),
        employment_status="ACTIVE",
        **body.model_dump(),
    )
    db.add(employee)
    db.flush()
    audit.record(db, "EMPLOYEE_CREATED", "CREATE", "employees", employee.employee_id, user,
                 new_values={"email": employee.email})
    db.commit()
    return EmployeeOut.model_validate(employee)


@router.get("/departments", response_model=List[DepartmentOut])
def list_departments(
    _user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)
) -> List[DepartmentOut]:
    return [DepartmentOut.model_validate(d) for d in EmployeeRepository(db).departments()]


@router.get("/teams", response_model=List[TeamOut])
def list_teams(
    user: UserAccount = Depends(require_permission("view_team_tickets")), db: Session = Depends(get_db)
) -> List[TeamOut]:
    teams = EmployeeRepository(db).teams()
    return [TeamOut.model_validate(t) for t in teams]


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(
    employee_id: str, user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)
) -> EmployeeOut:
    employee = (
        db.query(Employee)
        .filter(Employee.employee_id == employee_id, Employee.is_deleted.is_(False))
        .first()
    )
    if employee is None or not _can_see_employee(db, user, employee):
        raise NotFoundError("Employee %s not found" % employee_id)
    return EmployeeOut.model_validate(employee)
