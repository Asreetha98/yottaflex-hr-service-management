from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_permission
from app.models.sla import BusinessCalendar
from app.models.user import UserAccount
from app.schemas import Page
from app.schemas.sla import BusinessCalendarOut, SLAMetrics, SLAOut
from app.services.sla_service import sla_service
from app.services.ticket_service import ticket_service

router = APIRouter(prefix="/sla", tags=["sla"])


def _visible_ids(db: Session, user: UserAccount):
    """SLA data is limited to tickets the caller may see."""
    return ticket_service.visible_query(db, user).with_entities(
        __import__("app.models.ticket", fromlist=["Ticket"]).Ticket.ticket_id
    )


@router.get("/metrics", response_model=SLAMetrics)
def metrics(user: UserAccount = Depends(require_permission("view_all_tickets")), db: Session = Depends(get_db)) -> SLAMetrics:
    ids = [row[0] for row in _visible_ids(db, user).all()]
    return SLAMetrics(**sla_service.metrics(db, allowed_ticket_ids=ids or ["__none__"]))


@router.get("", response_model=Page[SLAOut])
def list_slas(
    status: Optional[str] = None,
    policy: Optional[str] = None,
    breached: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: UserAccount = Depends(require_permission("view_all_tickets")),
    db: Session = Depends(get_db),
) -> Page[SLAOut]:
    ids = [row[0] for row in _visible_ids(db, user).all()]
    items, total = sla_service.list_slas(db, status, policy, breached, ids or ["__none__"], skip, limit)
    return Page[SLAOut](items=[SLAOut.model_validate(s) for s in items], total=total, skip=skip, limit=limit)


@router.post("/check-breaches", response_model=SLAMetrics)
def check_breaches(user: UserAccount = Depends(require_permission("manage_config")), db: Session = Depends(get_db)) -> SLAMetrics:
    sla_service.detect_breaches(db)
    db.commit()
    return SLAMetrics(**sla_service.metrics(db))


@router.get("/calendar", response_model=BusinessCalendarOut)
def calendar(_user: UserAccount = Depends(require_permission("view_all_tickets")), db: Session = Depends(get_db)) -> BusinessCalendarOut:
    row = sla_service.get_calendar_row(db)
    if row is None:
        from app.exceptions import NotFoundError

        raise NotFoundError("No business calendar configured")
    return BusinessCalendarOut.model_validate(row)
