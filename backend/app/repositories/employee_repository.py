from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.employee import Department, Employee, Team
from app.repositories.base_repository import BaseRepository


class EmployeeRepository(BaseRepository[Employee]):
    def __init__(self, db: Session) -> None:
        super().__init__(Employee, db)

    def by_email(self, email: str) -> Optional[Employee]:
        return self._query().filter(Employee.email == email).first()

    def by_department(self, department_id: str, skip: int = 0, limit: int = 50) -> List[Employee]:
        return self.list(skip, limit, [Employee.department_id == department_id], Employee.employee_id)

    def direct_reports(self, manager_id: str) -> List[Employee]:
        return self.list(0, 1000, [Employee.manager_id == manager_id], Employee.employee_id)

    def departments(self) -> List[Department]:
        return (
            self.db.query(Department)
            .filter(Department.is_deleted.is_(False))
            .order_by(Department.department_id)
            .all()
        )

    def teams(self) -> List[Team]:
        return self.db.query(Team).filter(Team.is_deleted.is_(False)).order_by(Team.team_id).all()
