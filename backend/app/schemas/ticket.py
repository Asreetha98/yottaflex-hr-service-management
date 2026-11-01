from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas import ORMModel


class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=3, max_length=10000)
    channel: str = "PORTAL"


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    is_internal: bool = False


class MessageOut(ORMModel):
    message_id: str
    ticket_id: str
    sequence_number: int
    sender_user_id: Optional[str] = None
    sender_type: str
    message_type: str
    is_internal: bool
    body: str
    created_at: datetime


class TicketEventOut(ORMModel):
    event_id: str
    ticket_id: str
    event_type: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    actor_user_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime


class AssignmentOut(ORMModel):
    assignment_id: str
    ticket_id: str
    team_id: str
    assigned_user_id: Optional[str] = None
    assignment_type: str
    routing_reason: str
    rule_reference: Optional[str] = None
    is_current: bool
    assigned_at: datetime


class EscalationOut(ORMModel):
    escalation_id: str
    ticket_id: str
    from_team_id: Optional[str] = None
    to_team_id: Optional[str] = None
    escalation_level: str
    reason_code: str
    reason: str
    escalated_at: datetime
    status: str


class ResolutionOut(ORMModel):
    resolution_id: str
    ticket_id: str
    resolution_type: str
    summary: str
    resolution_text: str
    policy_version_id: Optional[str] = None
    citation_id: Optional[str] = None
    article_id: Optional[str] = None
    resolved_by: str
    resolved_at: datetime
    satisfaction_score: Optional[int] = None
    was_reopened: bool = False


class TicketOut(ORMModel):
    ticket_id: str
    requester_id: str
    subject: str
    description: str
    category_code: Optional[str] = None
    priority: str
    status: str
    channel: str
    is_sensitive: bool
    access_level: str
    sensitive_patterns: Optional[List[str]] = None
    classification_confidence: Optional[float] = None
    classification_explanation: Optional[Dict[str, Any]] = None
    is_ambiguous: bool = False
    assigned_team_id: Optional[str] = None
    assigned_user_id: Optional[str] = None
    reopen_count: int = 0
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class TicketDetail(TicketOut):
    messages: List[MessageOut] = []
    events: List[TicketEventOut] = []
    assignments: List[AssignmentOut] = []
    escalations: List[EscalationOut] = []
    resolutions: List[ResolutionOut] = []


class AssignRequest(BaseModel):
    team_id: Optional[str] = None
    assignee_user_id: Optional[str] = None


class EscalateRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)
    to_team_id: Optional[str] = None


class ResolveRequest(BaseModel):
    resolution_type: str
    summary: str = Field(min_length=3, max_length=500)
    resolution_text: str = Field(min_length=3)
    policy_version_id: Optional[str] = None
    article_id: Optional[str] = None
    citation_id: Optional[str] = None


class ReopenRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)
