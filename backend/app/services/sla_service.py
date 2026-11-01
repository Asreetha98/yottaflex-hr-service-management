"""SLA persistence: creation, pause / resume, first response, resolution and breach detection."""

from datetime import datetime, time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.constants import DEFAULT_CALENDAR_ID, OPEN_STATUSES
from app.exceptions import BusinessRuleError, NotFoundError
from app.models.base import utcnow
from app.models.sla import SLA, BusinessCalendar, HolidayCalendar, SLAPauseEvent
from app.models.ticket import Ticket
from app.rules import sla_engine as engine
from app.services.events import record_ticket_event
from app.services.ids import next_id


class SLAService:
    # ------------------------------------------------------------------ #
    # Calendar
    # ------------------------------------------------------------------ #
    def get_calendar_row(self, db: Session, calendar_id: Optional[str] = None) -> Optional[BusinessCalendar]:
        query = db.query(BusinessCalendar).filter(BusinessCalendar.is_deleted.is_(False))
        if calendar_id:
            return query.filter(BusinessCalendar.calendar_id == calendar_id).first()
        return query.filter(BusinessCalendar.is_default.is_(True)).first() or query.first()

    def load_calendar(self, db: Session, calendar_id: Optional[str] = None) -> Tuple[engine.BusinessCalendar, str]:
        """Return the engine calendar and its id (falls back to Mon-Fri 09-17 UTC)."""
        row = self.get_calendar_row(db, calendar_id)
        if row is None:
            return engine.DEFAULT_CALENDAR, DEFAULT_CALENDAR_ID
        holidays = [
            h.holiday_date
            for h in db.query(HolidayCalendar)
            .filter(HolidayCalendar.calendar_id == row.calendar_id, HolidayCalendar.is_deleted.is_(False))
            .all()
        ]
        calendar = engine.BusinessCalendar.from_values(
            work_days=row.work_days or (0, 1, 2, 3, 4),
            start=row.start_time or time(9, 0),
            end=row.end_time or time(17, 0),
            holidays=holidays,
        )
        return calendar, row.calendar_id

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def create_sla(
        self,
        db: Session,
        ticket: Ticket,
        category_code: str,
        priority: str,
        is_sensitive: bool,
        team_type: Optional[str] = None,
        started_at: Optional[datetime] = None,
    ) -> SLA:
        existing = db.query(SLA).filter(SLA.ticket_id == ticket.ticket_id).first()
        if existing is not None:
            return existing
        calendar, calendar_id = self.load_calendar(db)
        started = started_at or ticket.created_at
        deadline = engine.calculate_sla_deadline(
            started, category_code, priority, is_sensitive, team_type, calendar
        )
        sla = SLA(
            sla_id="SLA-%s" % ticket.ticket_id,
            ticket_id=ticket.ticket_id,
            calendar_id=calendar_id,
            sla_policy=deadline.sla_policy,
            priority=priority,
            target_hours=deadline.target_hours,
            first_response_target_hours=deadline.first_response_target_hours,
            started_at=deadline.started_at,
            due_at=deadline.due_at,
            first_response_due_at=deadline.first_response_due_at,
            status=engine.ACTIVE,
        )
        db.add(sla)
        db.flush()
        return sla

    def get_for_ticket(self, db: Session, ticket_id: str) -> Optional[SLA]:
        return db.query(SLA).filter(SLA.ticket_id == ticket_id).first()

    def open_pause(self, db: Session, sla: SLA) -> Optional[SLAPauseEvent]:
        return (
            db.query(SLAPauseEvent)
            .filter(SLAPauseEvent.sla_id == sla.sla_id, SLAPauseEvent.resumed_at.is_(None))
            .first()
        )

    def pause(
        self,
        db: Session,
        ticket: Ticket,
        reason: str = "AWAITING_CLARIFICATION",
        actor_user_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Optional[SLAPauseEvent]:
        sla = self.get_for_ticket(db, ticket.ticket_id)
        if sla is None:
            return None
        if self.open_pause(db, sla) is not None:
            raise BusinessRuleError("SLA already has an open pause", "SLA_ALREADY_PAUSED")
        when = now or utcnow()
        pause = SLAPauseEvent(
            pause_id=next_id(db, SLAPauseEvent.pause_id, "PAU-", 6),
            sla_id=sla.sla_id,
            reason=reason,
            paused_at=when,
            paused_by=actor_user_id,
            created_at=when,
        )
        db.add(pause)
        sla.status = engine.PAUSED
        db.flush()
        record_ticket_event(
            db, ticket.ticket_id, "SLA_PAUSED", actor_user_id=actor_user_id,
            details={"reason": reason}, created_at=when,
        )
        return pause

    def resume(
        self,
        db: Session,
        ticket: Ticket,
        actor_user_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Optional[SLAPauseEvent]:
        sla = self.get_for_ticket(db, ticket.ticket_id)
        if sla is None:
            return None
        pause = self.open_pause(db, sla)
        if pause is None:
            return None
        when = now or utcnow()
        calendar, _ = self.load_calendar(db, sla.calendar_id)
        result = engine.resume_sla(sla.due_at, pause.paused_at, when, calendar)
        pause.resumed_at = when
        pause.business_minutes_paused = result.business_minutes_paused
        sla.total_paused_business_minutes += result.business_minutes_paused
        sla.due_at = result.new_due_at
        if sla.first_response_due_at is not None and sla.first_response_at is None:
            sla.first_response_due_at = engine.BusinessHoursCalculator(calendar).add_business_minutes(
                sla.first_response_due_at, result.business_minutes_paused
            )
        sla.status = engine.ACTIVE
        db.flush()
        record_ticket_event(
            db, ticket.ticket_id, "SLA_RESUMED", actor_user_id=actor_user_id,
            details={"business_minutes_paused": result.business_minutes_paused,
                     "new_due_at": result.new_due_at.isoformat()},
            created_at=when,
        )
        return pause

    def record_first_response(self, db: Session, ticket: Ticket, when: Optional[datetime] = None) -> None:
        when = when or utcnow()
        if ticket.first_response_at is None:
            ticket.first_response_at = when
        sla = self.get_for_ticket(db, ticket.ticket_id)
        if sla is not None and sla.first_response_at is None:
            sla.first_response_at = when
        db.flush()

    def mark_resolved(self, db: Session, ticket: Ticket, resolved_at: datetime) -> Optional[SLA]:
        sla = self.get_for_ticket(db, ticket.ticket_id)
        if sla is None:
            return None
        if self.open_pause(db, sla) is not None:
            self.resume(db, ticket, now=resolved_at)
        sla.resolved_at = resolved_at
        if resolved_at > sla.due_at:
            sla.status = engine.BREACHED
            if not sla.is_breached:
                sla.is_breached = True
                sla.breached_at = sla.due_at
        else:
            sla.status = engine.MET
        db.flush()
        return sla

    def reopen(self, db: Session, ticket: Ticket) -> Optional[SLA]:
        """A reopened ticket gets its clock running again (resolved state is cleared)."""
        sla = self.get_for_ticket(db, ticket.ticket_id)
        if sla is None:
            return None
        sla.resolved_at = None
        sla.status = engine.BREACHED if sla.is_breached else engine.ACTIVE
        db.flush()
        return sla

    # ------------------------------------------------------------------ #
    # Monitoring
    # ------------------------------------------------------------------ #
    def evaluate(self, db: Session, sla: SLA, now: Optional[datetime] = None) -> engine.SLAStatusResult:
        calendar, _ = self.load_calendar(db, sla.calendar_id)
        return engine.evaluate_sla_status(
            started_at=sla.started_at,
            due_at=sla.due_at,
            target_hours=sla.target_hours,
            now=now or utcnow(),
            resolved_at=sla.resolved_at,
            is_paused=sla.status == engine.PAUSED,
            paused_business_minutes=sla.total_paused_business_minutes,
            calendar=calendar,
        )

    def detect_breaches(self, db: Session, now: Optional[datetime] = None) -> List[SLA]:
        """Mark every unresolved, un-paused SLA past its deadline as BREACHED (once)."""
        when = now or utcnow()
        candidates = (
            db.query(SLA)
            .join(Ticket, Ticket.ticket_id == SLA.ticket_id)
            .filter(
                Ticket.status.in_(OPEN_STATUSES),
                Ticket.is_deleted.is_(False),
                SLA.status.in_([engine.ACTIVE, engine.PAUSED]),
                SLA.due_at < when,
            )
            .all()
        )
        newly: List[SLA] = []
        for sla in candidates:
            if sla.status == engine.PAUSED:
                continue  # clock is stopped
            sla.status = engine.BREACHED
            if not sla.is_breached:
                sla.is_breached = True
                sla.breached_at = sla.due_at
                record_ticket_event(
                    db, sla.ticket_id, "SLA_BREACHED",
                    details={"due_at": sla.due_at.isoformat()}, created_at=when,
                )
                newly.append(sla)
        db.flush()
        return newly

    def list_slas(
        self,
        db: Session,
        status: Optional[str] = None,
        policy: Optional[str] = None,
        breached_only: bool = False,
        allowed_ticket_ids: Optional[Any] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[SLA], int]:
        query = db.query(SLA).join(Ticket, Ticket.ticket_id == SLA.ticket_id).filter(Ticket.is_deleted.is_(False))
        if status:
            query = query.filter(SLA.status == status)
        if policy:
            query = query.filter(SLA.sla_policy == policy)
        if breached_only:
            query = query.filter(SLA.is_breached.is_(True))
        if allowed_ticket_ids is not None:
            query = query.filter(SLA.ticket_id.in_(allowed_ticket_ids))
        total = query.count()
        items = query.order_by(SLA.due_at.asc(), SLA.sla_id.asc()).offset(skip).limit(limit).all()
        return items, total

    def metrics(self, db: Session, now: Optional[datetime] = None, allowed_ticket_ids: Optional[Any] = None) -> Dict[str, Any]:
        when = now or utcnow()
        query = db.query(SLA).join(Ticket, Ticket.ticket_id == SLA.ticket_id).filter(Ticket.is_deleted.is_(False))
        if allowed_ticket_ids is not None:
            query = query.filter(SLA.ticket_id.in_(allowed_ticket_ids))
        slas = query.all()
        total = len(slas)
        met = sum(1 for s in slas if s.status == engine.MET)
        breached = sum(1 for s in slas if s.is_breached or s.status == engine.BREACHED)
        paused = sum(1 for s in slas if s.status == engine.PAUSED)
        active = sum(1 for s in slas if s.status == engine.ACTIVE)
        warning = 0
        for s in slas:
            if s.status == engine.ACTIVE and s.resolved_at is None:
                if self.evaluate(db, s, when).is_warning:
                    warning += 1
        completed = met + sum(1 for s in slas if s.status == engine.BREACHED and s.resolved_at is not None)
        by_policy: Dict[str, Dict[str, int]] = {}
        for s in slas:
            bucket = by_policy.setdefault(s.sla_policy, {"total": 0, "met": 0, "breached": 0})
            bucket["total"] += 1
            bucket["met"] += 1 if s.status == engine.MET else 0
            bucket["breached"] += 1 if (s.is_breached or s.status == engine.BREACHED) else 0
        return {
            "total": total,
            "active": active,
            "paused": paused,
            "met": met,
            "breached": breached,
            "warning": warning,
            "compliance_rate": round(met / completed, 4) if completed else None,
            "by_policy": by_policy,
        }

    def require(self, db: Session, ticket_id: str) -> SLA:
        sla = self.get_for_ticket(db, ticket_id)
        if sla is None:
            raise NotFoundError("SLA for ticket %s not found" % ticket_id)
        return sla


sla_service = SLAService()
