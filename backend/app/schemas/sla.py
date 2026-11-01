from datetime import date, datetime, time
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.schemas import ORMModel


class SLAOut(ORMModel):
    sla_id: str
    ticket_id: str
    sla_policy: str
    priority: str
    target_hours: float
    first_response_target_hours: Optional[float] = None
    started_at: datetime
    due_at: datetime
    first_response_due_at: Optional[datetime] = None
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    total_paused_business_minutes: int = 0
    status: str
    is_breached: bool = False
    breached_at: Optional[datetime] = None


class SLADetail(SLAOut):
    elapsed_hours: float = 0.0
    remaining_hours: float = 0.0
    percent_consumed: float = 0.0
    is_warning: bool = False


class SLAPolicyBucket(BaseModel):
    total: int
    met: int
    breached: int


class SLAMetrics(BaseModel):
    total: int
    active: int
    paused: int
    met: int
    breached: int
    warning: int
    compliance_rate: Optional[float] = None
    by_policy: Dict[str, SLAPolicyBucket] = {}


class HolidayOut(ORMModel):
    holiday_id: str
    holiday_date: date
    name: str


class BusinessCalendarOut(ORMModel):
    calendar_id: str
    name: str
    timezone: str
    work_days: List[int]
    start_time: time
    end_time: time
    is_default: bool
    holidays: List[HolidayOut] = []
