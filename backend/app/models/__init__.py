"""Import every model so ``Base.metadata`` is fully populated."""

from app.models.audit import AuditLog
from app.models.base import Base
from app.models.employee import Department, Employee, Team
from app.models.knowledge import Category, KnowledgeArticle, article_categories
from app.models.policy import PolicyAudience, PolicyCitation, PolicyDocument, PolicyVersion
from app.models.resolution import Resolution
from app.models.rules import CategoryRule, ClarificationTemplate, RoutingRule
from app.models.sla import SLA, BusinessCalendar, HolidayCalendar, SLAPauseEvent
from app.models.ticket import Assignment, Escalation, Message, Ticket, TicketEvent
from app.models.user import Permission, Role, UserAccount, role_permissions, user_roles

__all__ = [
    "Base",
    "AuditLog",
    "Department",
    "Employee",
    "Team",
    "Category",
    "KnowledgeArticle",
    "article_categories",
    "PolicyAudience",
    "PolicyCitation",
    "PolicyDocument",
    "PolicyVersion",
    "Resolution",
    "CategoryRule",
    "ClarificationTemplate",
    "RoutingRule",
    "SLA",
    "BusinessCalendar",
    "HolidayCalendar",
    "SLAPauseEvent",
    "Assignment",
    "Escalation",
    "Message",
    "Ticket",
    "TicketEvent",
    "Permission",
    "Role",
    "UserAccount",
    "role_permissions",
    "user_roles",
]
