from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_permission
from app.models.employee import Employee
from app.models.user import UserAccount
from app.schemas import Page
from app.schemas.policy import (
    PolicyCitationOut,
    PolicyDocumentCreate,
    PolicyDocumentOut,
    PolicyValidityOut,
    PolicyVersionCreate,
    PolicyVersionOut,
    PolicyVersionUpdate,
    PublishRequest,
)
from app.services.policy_service import policy_service

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("", response_model=Page[PolicyDocumentOut])
def list_policies(
    status: Optional[str] = None,
    category_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _user: UserAccount = Depends(require_permission("view_knowledge")),
    db: Session = Depends(get_db),
) -> Page[PolicyDocumentOut]:
    items, total = policy_service.list_policies(db, status, category_id, skip, limit)
    return Page[PolicyDocumentOut](items=[PolicyDocumentOut.model_validate(p) for p in items], total=total, skip=skip, limit=limit)


@router.post("", response_model=PolicyDocumentOut, status_code=201)
def create_policy(
    body: PolicyDocumentCreate,
    user: UserAccount = Depends(require_permission("manage_policies")),
    db: Session = Depends(get_db),
) -> PolicyDocumentOut:
    policy = policy_service.create_policy(
        db, body.title, body.owner_department_id, user, body.description, body.category_id
    )
    db.commit()
    return PolicyDocumentOut.model_validate(policy)


@router.get("/{policy_id}", response_model=PolicyDocumentOut)
def get_policy(policy_id: str, _user: UserAccount = Depends(require_permission("view_knowledge")), db: Session = Depends(get_db)) -> PolicyDocumentOut:
    return PolicyDocumentOut.model_validate(policy_service.get_policy(db, policy_id))


@router.get("/{policy_id}/versions", response_model=List[PolicyVersionOut])
def list_versions(policy_id: str, user: UserAccount = Depends(require_permission("view_knowledge")), db: Session = Depends(get_db)) -> List[PolicyVersionOut]:
    versions = policy_service.list_versions(db, policy_id)
    # Drafts are only visible to policy managers.
    if "manage_policies" not in _perms(user):
        versions = [v for v in versions if v.status != "DRAFT"]
    return [PolicyVersionOut.model_validate(v) for v in versions]


def _perms(user: UserAccount):
    from app.security.permissions import permissions_for_roles

    return permissions_for_roles(user.role_names)


@router.post("/{policy_id}/versions", response_model=PolicyVersionOut, status_code=201)
def create_version(
    policy_id: str, body: PolicyVersionCreate,
    user: UserAccount = Depends(require_permission("manage_policies")), db: Session = Depends(get_db),
) -> PolicyVersionOut:
    version = policy_service.create_version(
        db, policy_id, body.title, body.content, user, body.summary, body.effective_from, body.effective_to,
        [(a.audience_type, a.audience_value) for a in body.audiences],
    )
    db.commit()
    db.refresh(version)
    return PolicyVersionOut.model_validate(version)


@router.get("/{policy_id}/effective", response_model=PolicyValidityOut)
def effective_version(
    policy_id: str,
    reference_date: Optional[date] = None,
    employee_id: Optional[str] = None,
    _user: UserAccount = Depends(require_permission("view_knowledge")),
    db: Session = Depends(get_db),
) -> PolicyValidityOut:
    employee = db.query(Employee).filter(Employee.employee_id == employee_id).first() if employee_id else None
    result = policy_service.effective_version(db, policy_id, reference_date, employee)
    return PolicyValidityOut(
        policy_id=result.policy_id,
        reference_date=result.reference_date,
        version_id=result.version.version_id if result.version else None,
        exception_code=result.exception.code if result.exception else None,
        exception_message=result.exception.message if result.exception else None,
        latest_created=result.latest_created.version_id if result.latest_created else None,
        latest_published=result.latest_published.version_id if result.latest_published else None,
        currently_effective=result.currently_effective.version_id if result.currently_effective else None,
        historically_effective=result.historically_effective.version_id if result.historically_effective else None,
        overlap_detected=result.overlap_detected,
        explanation=result.explanation,
    )


@router.get("/versions/{version_id}", response_model=PolicyVersionOut)
def get_version(version_id: str, _user: UserAccount = Depends(require_permission("view_knowledge")), db: Session = Depends(get_db)) -> PolicyVersionOut:
    return PolicyVersionOut.model_validate(policy_service.get_version(db, version_id))


@router.get("/versions/{version_id}/citations", response_model=List[PolicyCitationOut])
def version_citations(version_id: str, _user: UserAccount = Depends(require_permission("view_knowledge")), db: Session = Depends(get_db)) -> List[PolicyCitationOut]:
    policy_service.get_version(db, version_id)
    from app.repositories.policy_repository import PolicyRepository

    return [PolicyCitationOut.model_validate(c) for c in PolicyRepository(db).citations(version_id)]


@router.patch("/versions/{version_id}", response_model=PolicyVersionOut)
def update_version(
    version_id: str, body: PolicyVersionUpdate,
    user: UserAccount = Depends(require_permission("manage_policies")), db: Session = Depends(get_db),
) -> PolicyVersionOut:
    version = policy_service.update_draft(db, version_id, user, **body.model_dump(exclude_unset=True))
    db.commit()
    return PolicyVersionOut.model_validate(version)


@router.post("/versions/{version_id}/publish", response_model=PolicyVersionOut)
def publish(
    version_id: str, body: PublishRequest,
    user: UserAccount = Depends(require_permission("manage_policies")), db: Session = Depends(get_db),
) -> PolicyVersionOut:
    version = policy_service.publish_version(db, version_id, user, body.effective_from)
    db.commit()
    return PolicyVersionOut.model_validate(version)


@router.post("/versions/{version_id}/archive", response_model=PolicyVersionOut)
def archive(version_id: str, user: UserAccount = Depends(require_permission("manage_policies")), db: Session = Depends(get_db)) -> PolicyVersionOut:
    version = policy_service.archive_version(db, version_id, user)
    db.commit()
    return PolicyVersionOut.model_validate(version)


@router.post("/{policy_id}/retire", response_model=PolicyDocumentOut)
def retire(policy_id: str, user: UserAccount = Depends(require_permission("manage_policies")), db: Session = Depends(get_db)) -> PolicyDocumentOut:
    policy = policy_service.retire_policy(db, policy_id, user)
    db.commit()
    return PolicyDocumentOut.model_validate(policy)
