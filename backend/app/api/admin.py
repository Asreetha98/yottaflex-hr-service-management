from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.constants import ROLE_NAMES
from app.dependencies import get_db, require_permission
from app.exceptions import ConflictError, NotFoundError
from app.models.audit import AuditLog
from app.models.base import utcnow
from app.models.employee import Employee
from app.models.knowledge import Category
from app.models.rules import CategoryRule, ClarificationTemplate, RoutingRule
from app.models.user import Role, UserAccount, user_roles
from app.schemas import ORMModel, Page
from app.security.password import hash_password
from app.services.audit_service import AuditService
from app.services.ids import next_id

router = APIRouter(prefix="/admin", tags=["admin"])
audit = AuditService()


# ----------------------------------------------------------------------- #
# Schemas (admin-only, kept local)
# ----------------------------------------------------------------------- #
class AdminUserOut(ORMModel):
    user_id: str
    username: str
    email: str
    employee_id: Optional[str] = None
    is_active: bool
    can_view_sensitive: bool
    roles: List[str] = []
    last_login_at: Optional[datetime] = None


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    employee_id: Optional[str] = None
    roles: List[str] = Field(default_factory=lambda: ["EMPLOYEE"])
    can_view_sensitive: bool = False


class AdminUserUpdate(BaseModel):
    is_active: Optional[bool] = None
    can_view_sensitive: Optional[bool] = None
    roles: Optional[List[str]] = None
    password: Optional[str] = Field(default=None, min_length=10, max_length=200)


class CategoryRuleOut(ORMModel):
    rule_id: str
    category_id: str
    rule_type: str
    term: str
    weight: float
    is_active: bool


class CategoryRuleCreate(BaseModel):
    category_code: str
    rule_type: str = Field(pattern="^(KEYWORD|PHRASE|SYNONYM)$")
    term: str = Field(min_length=1, max_length=255)
    weight: float = Field(default=1.0, gt=0)


class RoutingRuleOut(ORMModel):
    rule_id: str
    name: str
    category_id: Optional[str] = None
    is_sensitive: Optional[bool] = None
    priority_order: int
    target_team_id: str
    is_active: bool


class ClarificationTemplateOut(ORMModel):
    template_id: str
    category_id: str
    required_field: str
    question_text: str
    detection_keywords: List[str] = []
    display_order: int
    is_active: bool


class AuditLogOut(ORMModel):
    event_id: str
    event_type: str
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    actor_user_id: Optional[str] = None
    actor_role: Optional[str] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    created_at: datetime


def _set_roles(db: Session, user: UserAccount, names: List[str], assigned_by: str) -> None:
    unknown = [n for n in names if n not in ROLE_NAMES]
    if unknown:
        raise NotFoundError("Unknown role(s): %s" % ", ".join(unknown))
    roles = db.query(Role).filter(Role.name.in_(names)).all()
    user.roles = roles
    db.flush()
    db.execute(user_roles.update().where(user_roles.c.user_id == user.user_id).values(assigned_by=assigned_by))


def _admin_user(user: UserAccount) -> AdminUserOut:
    return AdminUserOut(
        user_id=user.user_id, username=user.username, email=user.email, employee_id=user.employee_id,
        is_active=user.is_active, can_view_sensitive=user.can_view_sensitive, roles=sorted(user.role_names),
        last_login_at=user.last_login_at,
    )


# ----------------------------------------------------------------------- #
# Users & roles
# ----------------------------------------------------------------------- #
@router.get("/users", response_model=Page[AdminUserOut])
def list_users(
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
    _admin: UserAccount = Depends(require_permission("manage_users")), db: Session = Depends(get_db),
) -> Page[AdminUserOut]:
    query = db.query(UserAccount).filter(UserAccount.is_deleted.is_(False))
    total = query.count()
    items = query.order_by(UserAccount.user_id).offset(skip).limit(limit).all()
    return Page[AdminUserOut](items=[_admin_user(u) for u in items], total=total, skip=skip, limit=limit)


@router.post("/users", response_model=AdminUserOut, status_code=201)
def create_user(
    body: AdminUserCreate, admin: UserAccount = Depends(require_permission("manage_users")),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    if db.query(UserAccount).filter((UserAccount.username == body.username) | (UserAccount.email == body.email)).first():
        raise ConflictError("Username or email already in use", "USER_EXISTS")
    if body.employee_id:
        if not db.query(Employee).filter(Employee.employee_id == body.employee_id).first():
            raise NotFoundError("Employee %s not found" % body.employee_id)
        if db.query(UserAccount).filter(UserAccount.employee_id == body.employee_id).first():
            raise ConflictError("Employee already has an account", "EMPLOYEE_HAS_ACCOUNT")
    user = UserAccount(
        user_id=next_id(db, UserAccount.user_id, "USR-", 6), employee_id=body.employee_id,
        username=body.username, email=body.email, password_hash=hash_password(body.password),
        can_view_sensitive=body.can_view_sensitive,
    )
    db.add(user)
    db.flush()
    _set_roles(db, user, body.roles, admin.user_id)
    audit.record(db, "USER_CREATED", "CREATE", "user_accounts", user.user_id, admin,
                 new_values={"username": user.username, "roles": body.roles})
    db.commit()
    return _admin_user(user)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: str, body: AdminUserUpdate, admin: UserAccount = Depends(require_permission("manage_users")),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    user = db.query(UserAccount).filter(UserAccount.user_id == user_id, UserAccount.is_deleted.is_(False)).first()
    if user is None:
        raise NotFoundError("User %s not found" % user_id)
    changes: Dict[str, Any] = {}
    if body.is_active is not None:
        user.is_active = body.is_active
        changes["is_active"] = body.is_active
    if body.can_view_sensitive is not None:
        user.can_view_sensitive = body.can_view_sensitive
        changes["can_view_sensitive"] = body.can_view_sensitive
    if body.roles is not None:
        _set_roles(db, user, body.roles, admin.user_id)
        changes["roles"] = body.roles
    if body.password:
        user.password_hash = hash_password(body.password)
        changes["password"] = "changed"
    audit.record(db, "USER_UPDATED", "UPDATE", "user_accounts", user_id, admin, new_values=changes)
    db.commit()
    return _admin_user(user)


# ----------------------------------------------------------------------- #
# Configurable rules
# ----------------------------------------------------------------------- #
@router.get("/category-rules", response_model=List[CategoryRuleOut])
def list_category_rules(
    category: Optional[str] = None,
    _admin: UserAccount = Depends(require_permission("manage_config")), db: Session = Depends(get_db),
) -> List[CategoryRuleOut]:
    query = db.query(CategoryRule).filter(CategoryRule.is_deleted.is_(False))
    if category:
        query = query.join(Category, Category.category_id == CategoryRule.category_id).filter(Category.code == category)
    return [CategoryRuleOut.model_validate(r) for r in query.order_by(CategoryRule.rule_id).all()]


@router.post("/category-rules", response_model=CategoryRuleOut, status_code=201)
def create_category_rule(
    body: CategoryRuleCreate, admin: UserAccount = Depends(require_permission("manage_config")),
    db: Session = Depends(get_db),
) -> CategoryRuleOut:
    from app.rules.classification_engine import normalize_text

    category = db.query(Category).filter(Category.code == body.category_code).first()
    if category is None:
        raise NotFoundError("Category %s not found" % body.category_code)
    rule = CategoryRule(
        rule_id=next_id(db, CategoryRule.rule_id, "CRL-", 6), category_id=category.category_id,
        rule_type=body.rule_type, term=normalize_text(body.term), weight=body.weight,
    )
    db.add(rule)
    db.flush()
    audit.record(db, "CATEGORY_RULE_CREATED", "CREATE", "category_rules", rule.rule_id, admin,
                 new_values={"category": body.category_code, "term": rule.term})
    db.commit()
    return CategoryRuleOut.model_validate(rule)


@router.delete("/category-rules/{rule_id}", status_code=204)
def delete_category_rule(
    rule_id: str, admin: UserAccount = Depends(require_permission("manage_config")), db: Session = Depends(get_db),
) -> None:
    rule = db.query(CategoryRule).filter(CategoryRule.rule_id == rule_id, CategoryRule.is_deleted.is_(False)).first()
    if rule is None:
        raise NotFoundError("Rule %s not found" % rule_id)
    rule.soft_delete()
    audit.record(db, "CATEGORY_RULE_DELETED", "DELETE", "category_rules", rule_id, admin)
    db.commit()


@router.get("/routing-rules", response_model=List[RoutingRuleOut])
def list_routing_rules(_admin: UserAccount = Depends(require_permission("manage_config")), db: Session = Depends(get_db)) -> List[RoutingRuleOut]:
    rows = db.query(RoutingRule).filter(RoutingRule.is_deleted.is_(False)).order_by(RoutingRule.priority_order).all()
    return [RoutingRuleOut.model_validate(r) for r in rows]


@router.get("/clarification-templates", response_model=List[ClarificationTemplateOut])
def list_templates(_admin: UserAccount = Depends(require_permission("manage_config")), db: Session = Depends(get_db)) -> List[ClarificationTemplateOut]:
    rows = db.query(ClarificationTemplate).filter(ClarificationTemplate.is_deleted.is_(False)).order_by(
        ClarificationTemplate.category_id, ClarificationTemplate.display_order).all()
    return [ClarificationTemplateOut.model_validate(r) for r in rows]


# ----------------------------------------------------------------------- #
# Audit log
# ----------------------------------------------------------------------- #
@router.get("/audit-logs", response_model=Page[AuditLogOut])
def audit_logs(
    event_type: Optional[str] = None, entity_type: Optional[str] = None, entity_id: Optional[str] = None,
    actor_user_id: Optional[str] = None, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
    _admin: UserAccount = Depends(require_permission("view_audit_logs")), db: Session = Depends(get_db),
) -> Page[AuditLogOut]:
    items, total = audit.list_events(db, event_type, entity_type, entity_id, actor_user_id, skip, limit)
    return Page[AuditLogOut](items=[AuditLogOut.model_validate(a) for a in items], total=total, skip=skip, limit=limit)
