from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class OverviewMetrics(BaseModel):
    total_tickets: int
    open_tickets: int
    resolved_tickets: int
    awaiting_clarification: int
    escalated_tickets: int
    sensitive_tickets: int
    created_last_24h: int
    sla_compliance_rate: Optional[float] = None
    sla_breached: int
    sla_warning: int


class DailyVolume(BaseModel):
    date: str
    count: int


class TicketMetrics(BaseModel):
    total: int
    by_status: Dict[str, int]
    by_priority: Dict[str, int]
    by_category: Dict[str, int]
    by_channel: Dict[str, int]
    daily_volume: List[DailyVolume]
    ambiguous: int


class PerformanceMetrics(BaseModel):
    avg_resolution_business_hours: Optional[float] = None
    avg_first_response_business_hours: Optional[float] = None
    sla_compliance_rate: Optional[float] = None
    sla_by_policy: Dict[str, Dict[str, int]] = {}
    reopen_rate: Optional[float] = None
    escalation_rate: Optional[float] = None
    avg_satisfaction: Optional[float] = None
    resolved_count: int = 0


class EvaluationMetrics(BaseModel):
    available: bool
    reason: Optional[str] = None
    evaluated: int = 0
    category_accuracy: Optional[float] = None
    sensitive_precision: Optional[float] = None
    sensitive_recall: Optional[float] = None
    sensitive_counts: Dict[str, int] = {}
    per_category: Dict[str, Dict[str, Optional[float]]] = {}
    confusion: Dict[str, Dict[str, int]] = {}
