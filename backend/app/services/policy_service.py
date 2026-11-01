"""Policy CRUD, version management, publish / archive, and engine adapters."""

from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.base import utcnow
from app.models.employee import Employee
from app.models.policy import PolicyAudience, PolicyCitation, PolicyDocument, PolicyVersion
from app.models.user import UserAccount
from app.rules.policy_validity_engine import (
    PolicyValidityEngine,
    PolicyValidityResult,
    PolicyVersionData,
    build_employee_context,
)
from app.services.audit_service import AuditService
from app.services.ids import next_id

audit = AuditService()


def to_version_data(version: PolicyVersion) -> PolicyVersionData:
    return PolicyVersionData(
        version_id=version.version_id,
        policy_id=version.policy_id,
        version_number=version.version_number,
        status=version.status,
        effective_from=version.effective_from,
        effective_to=version.effective_to,
        published_at=version.published_at,
        created_at=version.created_at,
        audiences=tuple((a.audience_type, a.audience_value) for a in version.audiences),
        title=version.title,
    )


def employee_context(employee: Optional[Employee]) -> Dict[str, str]:
    if employee is None:
        return {}
    return build_employee_context(employee.department_id, employee.employment_type, employee.location)


class PolicyService:
    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def list_policies(
        self, db: Session, status: Optional[str] = None, category_id: Optional[str] = None,
        skip: int = 0, limit: int = 50,
    ) -> Tuple[List[PolicyDocument], int]:
        query = db.query(PolicyDocument).filter(PolicyDocument.is_deleted.is_(False))
        if status:
            query = query.filter(PolicyDocument.status == status)
        if category_id:
            query = query.filter(PolicyDocument.category_id == category_id)
        total = query.count()
        items = query.order_by(PolicyDocument.policy_id).offset(skip).limit(limit).all()
        return items, total

    def get_policy(self, db: Session, policy_id: str) -> PolicyDocument:
        policy = (
            db.query(PolicyDocument)
            .filter(PolicyDocument.policy_id == policy_id, PolicyDocument.is_deleted.is_(False))
            .first()
        )
        if policy is None:
            raise NotFoundError("Policy %s not found" % policy_id)
        return policy

    def get_version(self, db: Session, version_id: str) -> PolicyVersion:
        version = (
            db.query(PolicyVersion)
            .filter(PolicyVersion.version_id == version_id, PolicyVersion.is_deleted.is_(False))
            .first()
        )
        if version is None:
            raise NotFoundError("Policy version %s not found" % version_id)
        return version

    def list_versions(self, db: Session, policy_id: str) -> List[PolicyVersion]:
        self.get_policy(db, policy_id)
        return (
            db.query(PolicyVersion)
            .filter(PolicyVersion.policy_id == policy_id, PolicyVersion.is_deleted.is_(False))
            .order_by(PolicyVersion.version_number)
            .all()
        )

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #
    def create_policy(
        self, db: Session, title: str, owner_department_id: str, actor: Optional[UserAccount],
        description: Optional[str] = None, category_id: Optional[str] = None,
        policy_id: Optional[str] = None,
    ) -> PolicyDocument:
        policy = PolicyDocument(
            policy_id=policy_id or next_id(db, PolicyDocument.policy_id, "POL-HR-2026-", 3),
            title=title,
            description=description,
            category_id=category_id,
            owner_department_id=owner_department_id,
            status="ACTIVE",
        )
        db.add(policy)
        db.flush()
        audit.record(db, "POLICY_CREATED", "CREATE", "policy_documents", policy.policy_id, actor,
                     new_values={"title": title})
        return policy

    def create_version(
        self, db: Session, policy_id: str, title: str, content: str, actor: Optional[UserAccount],
        summary: Optional[str] = None, effective_from: Optional[date] = None,
        effective_to: Optional[date] = None, audiences: Optional[Iterable[Tuple[str, Optional[str]]]] = None,
    ) -> PolicyVersion:
        policy = self.get_policy(db, policy_id)
        if policy.status == "RETIRED":
            raise BusinessRuleError("Cannot add versions to a retired policy", "POLICY_RETIRED")
        existing = self.list_versions(db, policy_id)
        number = (existing[-1].version_number + 1) if existing else 1
        previous = next((v for v in reversed(existing) if v.status != "DRAFT"), None)
        version = PolicyVersion(
            version_id="VER-%s-%02d" % (policy_id, number),
            policy_id=policy_id,
            version_number=number,
            title=title,
            content=content,
            summary=summary,
            status="DRAFT",
            effective_from=effective_from,
            effective_to=effective_to,
            created_by=actor.user_id if actor else None,
            supersedes_version_id=previous.version_id if previous else None,
        )
        db.add(version)
        db.flush()
        for kind, value in (audiences or [("ALL", None)]):
            db.add(PolicyAudience(
                audience_id=next_id(db, PolicyAudience.audience_id, "AUD-", 6),
                version_id=version.version_id, audience_type=kind, audience_value=value,
            ))
            db.flush()
        db.refresh(version)
        audit.record(db, "POLICY_VERSION_CREATED", "CREATE", "policy_versions", version.version_id, actor,
                     new_values={"policy_id": policy_id, "version_number": number})
        return version

    def update_draft(
        self, db: Session, version_id: str, actor: Optional[UserAccount], **changes: Any
    ) -> PolicyVersion:
        version = self.get_version(db, version_id)
        if version.status != "DRAFT":
            raise BusinessRuleError(
                "Published versions are immutable; create a new version instead", "VERSION_IMMUTABLE"
            )
        allowed = {"title", "content", "summary", "effective_from", "effective_to"}
        old = {k: getattr(version, k) for k in changes if k in allowed}
        for key, value in changes.items():
            if key in allowed and value is not None:
                setattr(version, key, value)
        db.flush()
        audit.record(db, "POLICY_VERSION_UPDATED", "UPDATE", "policy_versions", version_id, actor,
                     old_values=old, new_values={k: changes[k] for k in old})
        return version

    def publish_version(
        self, db: Session, version_id: str, actor: Optional[UserAccount],
        effective_from: Optional[date] = None, now: Optional[datetime] = None,
    ) -> PolicyVersion:
        version = self.get_version(db, version_id)
        if version.status != "DRAFT":
            raise BusinessRuleError("Only DRAFT versions can be published", "NOT_DRAFT")
        if effective_from is not None:
            version.effective_from = effective_from
        if version.effective_from is None:
            raise BusinessRuleError("effective_from is required to publish", "EFFECTIVE_FROM_REQUIRED")
        if version.effective_to is not None and version.effective_to < version.effective_from:
            raise BusinessRuleError("effective_to precedes effective_from", "INVALID_WINDOW")

        others = [v for v in self.list_versions(db, version.policy_id)
                  if v.version_id != version.version_id and v.status in ("PUBLISHED", "ARCHIVED")]
        latest = max(others, key=lambda v: v.effective_from or date.min, default=None)
        if latest is not None and latest.effective_from and version.effective_from <= latest.effective_from:
            raise ConflictError(
                "effective_from must be later than %s (version %s)" % (latest.effective_from, latest.version_id),
                "EFFECTIVE_FROM_NOT_LATER",
            )
        if latest is not None and latest.effective_to is None:
            latest.effective_to = version.effective_from - timedelta(days=1)

        version.status = "PUBLISHED"
        version.published_at = now or utcnow()
        version.published_by = actor.user_id if actor else None
        db.flush()
        audit.record(db, "POLICY_PUBLISHED", "TRANSITION", "policy_versions", version.version_id, actor,
                     old_values={"status": "DRAFT"}, new_values={"status": "PUBLISHED",
                     "effective_from": version.effective_from})
        return version

    def archive_version(self, db: Session, version_id: str, actor: Optional[UserAccount]) -> PolicyVersion:
        version = self.get_version(db, version_id)
        if version.status == "ARCHIVED":
            raise BusinessRuleError("Version already archived", "ALREADY_ARCHIVED")
        previous = version.status
        version.status = "ARCHIVED"
        db.flush()
        audit.record(db, "POLICY_ARCHIVED", "TRANSITION", "policy_versions", version_id, actor,
                     old_values={"status": previous}, new_values={"status": "ARCHIVED"})
        return version

    def retire_policy(self, db: Session, policy_id: str, actor: Optional[UserAccount]) -> PolicyDocument:
        policy = self.get_policy(db, policy_id)
        policy.status = "RETIRED"
        db.flush()
        audit.record(db, "POLICY_RETIRED", "TRANSITION", "policy_documents", policy_id, actor,
                     new_values={"status": "RETIRED"})
        return policy

    def add_citation(
        self, db: Session, version_id: str, section_reference: str, excerpt: str,
        article_id: Optional[str] = None,
    ) -> PolicyCitation:
        self.get_version(db, version_id)
        citation = PolicyCitation(
            citation_id=next_id(db, PolicyCitation.citation_id, "CIT-", 6),
            version_id=version_id, article_id=article_id,
            section_reference=section_reference, excerpt=excerpt,
        )
        db.add(citation)
        db.flush()
        return citation

    # ------------------------------------------------------------------ #
    # Validity
    # ------------------------------------------------------------------ #
    def build_engine(self, db: Session, today: Optional[date] = None) -> PolicyValidityEngine:
        versions = (
            db.query(PolicyVersion)
            .join(PolicyDocument, PolicyDocument.policy_id == PolicyVersion.policy_id)
            .filter(PolicyVersion.is_deleted.is_(False), PolicyDocument.is_deleted.is_(False))
            .all()
        )
        policies = {
            p.policy_id: p.status
            for p in db.query(PolicyDocument).filter(PolicyDocument.is_deleted.is_(False)).all()
        }
        return PolicyValidityEngine(
            [to_version_data(v) for v in versions], policies, today=today or utcnow().date()
        )

    def effective_version(
        self, db: Session, policy_id: str, reference_date: Optional[date] = None,
        employee: Optional[Employee] = None, today: Optional[date] = None,
    ) -> PolicyValidityResult:
        engine = self.build_engine(db, today)
        ref = reference_date or engine.today
        return engine.get_effective_version(policy_id, ref, employee_audience=employee_context(employee))


policy_service = PolicyService()
