"""Deterministic SLA arithmetic on a business calendar.

* Business hours default to Monday-Friday 09:00-17:00 UTC.
* Weekends and holidays are skipped.
* All arithmetic is in whole minutes, so ``calculate_sla_deadline`` and
  ``calculate_elapsed_business_hours`` are exact inverses of each other.
* Pausing the clock pushes the deadline out by the *business* minutes spent paused.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, FrozenSet, Iterable, Optional, Tuple

from app.rules.classification_engine import contains_term, normalize_text

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
# Resolution targets in business hours.
SLA_TARGET_HOURS: Dict[str, Dict[str, float]] = {
    "PAYROLL": {"P1": 4, "P2": 8, "P3": 24},
    "LEAVE": {"P1": 8, "P2": 16, "P3": 48},
    "BENEFITS": {"P1": 8, "P2": 16, "P3": 48},
    "ONBOARDING": {"P1": 4, "P2": 8, "P3": 24},
    "GENERAL": {"P1": 8, "P2": 16, "P3": 48},
    "SENSITIVE": {"P1": 8, "P2": 16, "P3": 24},
}
SENSITIVE_FIRST_RESPONSE_HOURS = 2.0
WARNING_THRESHOLD = 0.8

P1_TERMS: Tuple[str, ...] = (
    "urgent", "asap", "immediately", "emergency", "not received", "not paid", "unpaid",
    "missing salary", "cannot access", "today",
)
P2_TERMS: Tuple[str, ...] = (
    "incorrect", "wrong", "error", "deadline", "this week", "delay", "delayed", "discrepancy",
)

ACTIVE = "ACTIVE"
PAUSED = "PAUSED"
MET = "MET"
BREACHED = "BREACHED"


class SLAError(ValueError):
    """Invalid SLA input (unknown priority, overlapping pause, ...)."""


# --------------------------------------------------------------------------- #
# Calendar
# --------------------------------------------------------------------------- #
def ensure_utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime (naive values are assumed to be UTC)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class BusinessCalendar:
    """Working days, hours and holidays used for SLA arithmetic."""

    work_days: FrozenSet[int] = frozenset({0, 1, 2, 3, 4})  # Monday=0
    start: time = time(9, 0)
    end: time = time(17, 0)
    holidays: FrozenSet[date] = frozenset()

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise SLAError("Business day end must be after start")
        if not self.work_days:
            raise SLAError("Calendar needs at least one working day")

    @classmethod
    def from_values(
        cls,
        work_days: Iterable[int] = (0, 1, 2, 3, 4),
        start: time = time(9, 0),
        end: time = time(17, 0),
        holidays: Iterable[date] = (),
    ) -> "BusinessCalendar":
        return cls(frozenset(work_days), start, end, frozenset(holidays))

    @property
    def minutes_per_day(self) -> int:
        return (self.end.hour * 60 + self.end.minute) - (self.start.hour * 60 + self.start.minute)

    def is_business_day(self, day: date) -> bool:
        return day.weekday() in self.work_days and day not in self.holidays

    def day_window(self, day: date) -> Tuple[datetime, datetime]:
        open_at = datetime.combine(day, self.start, tzinfo=timezone.utc)
        close_at = datetime.combine(day, self.end, tzinfo=timezone.utc)
        return open_at, close_at


DEFAULT_CALENDAR = BusinessCalendar()


# --------------------------------------------------------------------------- #
# Calculator
# --------------------------------------------------------------------------- #
class BusinessHoursCalculator:
    """Add / measure business time on a :class:`BusinessCalendar`."""

    # Guard against pathological calendars/holiday sets.
    MAX_DAYS_SCAN = 3660

    def __init__(self, calendar: Optional[BusinessCalendar] = None) -> None:
        self.calendar = calendar or DEFAULT_CALENDAR

    # -- positioning ---------------------------------------------------- #
    def next_business_open(self, moment: datetime) -> datetime:
        """Earliest instant ``>= moment`` that lies inside business hours.

        If ``moment`` is exactly the closing time it belongs to the *next* window.
        """
        moment = ensure_utc(moment)
        day = moment.date()
        for _ in range(self.MAX_DAYS_SCAN):
            if self.calendar.is_business_day(day):
                open_at, close_at = self.calendar.day_window(day)
                if moment < open_at:
                    return open_at
                if moment < close_at:
                    return moment
            day += timedelta(days=1)
            moment = datetime.combine(day, time(0, 0), tzinfo=timezone.utc)
        raise SLAError("No business day found within scan limit")

    # -- forward -------------------------------------------------------- #
    def add_business_minutes(self, start: datetime, minutes: int) -> datetime:
        """Return the instant that is ``minutes`` of business time after ``start``.

        ``minutes == 0`` returns ``start`` unchanged. A result that lands exactly on
        closing time is reported as the closing time (not next morning's opening).
        """
        start = ensure_utc(start)
        if minutes < 0:
            raise SLAError("minutes must be >= 0")
        if minutes == 0:
            return start

        remaining = int(minutes)
        cursor = self.next_business_open(start)
        for _ in range(self.MAX_DAYS_SCAN * 2):
            _, close_at = self.calendar.day_window(cursor.date())
            available = int((close_at - cursor).total_seconds() // 60)
            if remaining <= available:
                return cursor + timedelta(minutes=remaining)
            remaining -= available
            cursor = self.next_business_open(close_at)
        raise SLAError("Deadline beyond scan limit")

    def add_business_hours(self, start: datetime, hours: float) -> datetime:
        return self.add_business_minutes(start, int(round(hours * 60)))

    # -- elapsed -------------------------------------------------------- #
    def elapsed_business_minutes(self, start: datetime, end: datetime) -> int:
        """Whole business minutes between ``start`` and ``end`` (0 if ``end <= start``)."""
        start, end = ensure_utc(start), ensure_utc(end)
        if end <= start:
            return 0
        total = 0.0
        day = start.date()
        last = end.date()
        while day <= last:
            if self.calendar.is_business_day(day):
                open_at, close_at = self.calendar.day_window(day)
                lo = max(start, open_at)
                hi = min(end, close_at)
                if hi > lo:
                    total += (hi - lo).total_seconds()
            day += timedelta(days=1)
        return int(total // 60)

    def elapsed_business_hours(self, start: datetime, end: datetime) -> float:
        return round(self.elapsed_business_minutes(start, end) / 60.0, 4)


def calculate_elapsed_business_hours(
    start: datetime, end: datetime, calendar: Optional[BusinessCalendar] = None
) -> float:
    """Business hours between two instants on ``calendar`` (default Mon-Fri 09-17 UTC)."""
    return BusinessHoursCalculator(calendar).elapsed_business_hours(start, end)


# --------------------------------------------------------------------------- #
# Priority
# --------------------------------------------------------------------------- #
def derive_priority(subject: Optional[str], description: Optional[str], is_sensitive: bool = False) -> str:
    """P1 for sensitive/urgent text, P2 for error/delay wording, else P3."""
    if is_sensitive:
        return "P1"
    text = normalize_text("%s %s" % (subject or "", description or ""))
    if any(contains_term(text, term) for term in P1_TERMS):
        return "P1"
    if any(contains_term(text, term) for term in P2_TERMS):
        return "P2"
    return "P3"


# --------------------------------------------------------------------------- #
# Deadline
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SLADeadline:
    sla_policy: str
    priority: str
    target_hours: float
    started_at: datetime
    due_at: datetime
    first_response_target_hours: Optional[float] = None
    first_response_due_at: Optional[datetime] = None
    escalate_immediately: bool = False
    team: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "sla_policy": self.sla_policy,
            "priority": self.priority,
            "target_hours": self.target_hours,
            "started_at": self.started_at.isoformat(),
            "due_at": self.due_at.isoformat(),
            "first_response_target_hours": self.first_response_target_hours,
            "first_response_due_at": self.first_response_due_at.isoformat()
            if self.first_response_due_at
            else None,
            "escalate_immediately": self.escalate_immediately,
            "team": self.team,
        }


def get_target_hours(
    category: str,
    priority: str,
    is_sensitive: bool = False,
    config: Optional[Dict[str, Dict[str, float]]] = None,
) -> Tuple[str, float]:
    """Return ``(sla_policy, target_hours)``; sensitivity overrides the category row."""
    table = config or SLA_TARGET_HOURS
    policy = "SENSITIVE" if is_sensitive else (category if category in table else "GENERAL")
    row = table[policy]
    if priority not in row:
        raise SLAError("Unknown priority %r" % priority)
    return policy, float(row[priority])


def calculate_sla_deadline(
    created_at: datetime,
    category: str,
    priority: str,
    sensitivity: bool = False,
    team: Optional[str] = None,
    calendar: Optional[BusinessCalendar] = None,
    config: Optional[Dict[str, Dict[str, float]]] = None,
) -> SLADeadline:
    """Compute resolution (and, for sensitive cases, first-response) deadlines.

    The clock starts at ``created_at``; if that is outside business hours counting
    begins at the next opening.
    """
    created_at = ensure_utc(created_at)
    policy, target = get_target_hours(category, priority, sensitivity, config)
    calculator = BusinessHoursCalculator(calendar)
    due_at = calculator.add_business_hours(created_at, target)

    first_target: Optional[float] = None
    first_due: Optional[datetime] = None
    if sensitivity:
        first_target = SENSITIVE_FIRST_RESPONSE_HOURS
        first_due = calculator.add_business_hours(created_at, first_target)

    return SLADeadline(
        sla_policy=policy,
        priority=priority,
        target_hours=target,
        started_at=created_at,
        due_at=due_at,
        first_response_target_hours=first_target,
        first_response_due_at=first_due,
        escalate_immediately=sensitivity,
        team=team,
    )


# --------------------------------------------------------------------------- #
# Pause / resume
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PauseWindow:
    paused_at: datetime
    resumed_at: Optional[datetime] = None


@dataclass(frozen=True)
class ResumeResult:
    business_minutes_paused: int
    new_due_at: datetime


def assert_can_pause(pauses: Iterable[PauseWindow]) -> None:
    """Only one open pause per SLA; overlapping pauses are rejected."""
    if any(p.resumed_at is None for p in pauses):
        raise SLAError("SLA already has an open pause")


def resume_sla(
    due_at: datetime,
    paused_at: datetime,
    resumed_at: datetime,
    calendar: Optional[BusinessCalendar] = None,
) -> ResumeResult:
    """Close a pause: compute paused business minutes and push the deadline out by them."""
    paused_at, resumed_at = ensure_utc(paused_at), ensure_utc(resumed_at)
    if resumed_at < paused_at:
        raise SLAError("resumed_at cannot be before paused_at")
    calculator = BusinessHoursCalculator(calendar)
    minutes = calculator.elapsed_business_minutes(paused_at, resumed_at)
    return ResumeResult(minutes, calculator.add_business_minutes(ensure_utc(due_at), minutes))


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #
@dataclass
class SLAStatusResult:
    status: str
    is_breached: bool
    is_warning: bool
    elapsed_hours: float
    remaining_hours: float
    percent_consumed: float
    breached_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "is_breached": self.is_breached,
            "is_warning": self.is_warning,
            "elapsed_hours": self.elapsed_hours,
            "remaining_hours": self.remaining_hours,
            "percent_consumed": self.percent_consumed,
            "breached_at": self.breached_at.isoformat() if self.breached_at else None,
        }


def evaluate_sla_status(
    started_at: datetime,
    due_at: datetime,
    target_hours: float,
    now: datetime,
    resolved_at: Optional[datetime] = None,
    is_paused: bool = False,
    paused_business_minutes: int = 0,
    calendar: Optional[BusinessCalendar] = None,
) -> SLAStatusResult:
    """Classify an SLA as ACTIVE / PAUSED / MET / BREACHED.

    ``percent_consumed`` is net of paused time. A warning is raised at 80 % consumed.
    """
    calculator = BusinessHoursCalculator(calendar)
    started_at, due_at, now = ensure_utc(started_at), ensure_utc(due_at), ensure_utc(now)
    end = ensure_utc(resolved_at) if resolved_at else now
    gross_minutes = calculator.elapsed_business_minutes(started_at, end)
    net_minutes = max(0, gross_minutes - paused_business_minutes)
    elapsed_hours = round(net_minutes / 60.0, 4)
    percent = round(net_minutes / (target_hours * 60.0), 4) if target_hours else 0.0
    remaining = round(max(0.0, target_hours - elapsed_hours), 4)

    if resolved_at is not None:
        breached = ensure_utc(resolved_at) > due_at
        return SLAStatusResult(
            BREACHED if breached else MET,
            breached,
            False,
            elapsed_hours,
            remaining,
            percent,
            due_at if breached else None,
        )
    if is_paused:
        return SLAStatusResult(PAUSED, False, False, elapsed_hours, remaining, percent)
    if now > due_at:
        return SLAStatusResult(BREACHED, True, False, elapsed_hours, 0.0, percent, due_at)
    return SLAStatusResult(ACTIVE, False, percent >= WARNING_THRESHOLD, elapsed_hours, remaining, percent)


class SLAEngine:
    """Facade bundling the module functions around one calendar."""

    def __init__(self, calendar: Optional[BusinessCalendar] = None) -> None:
        self.calendar = calendar or DEFAULT_CALENDAR
        self.calculator = BusinessHoursCalculator(self.calendar)

    def calculate_sla_deadline(
        self,
        created_at: datetime,
        category: str,
        priority: str,
        sensitivity: bool = False,
        team: Optional[str] = None,
    ) -> SLADeadline:
        return calculate_sla_deadline(created_at, category, priority, sensitivity, team, self.calendar)

    def calculate_elapsed_business_hours(self, start: datetime, end: datetime) -> float:
        return self.calculator.elapsed_business_hours(start, end)

    def resume(self, due_at: datetime, paused_at: datetime, resumed_at: datetime) -> ResumeResult:
        return resume_sla(due_at, paused_at, resumed_at, self.calendar)

    def evaluate(self, **kwargs) -> SLAStatusResult:  # type: ignore[no-untyped-def]
        kwargs.setdefault("calendar", self.calendar)
        return evaluate_sla_status(**kwargs)
