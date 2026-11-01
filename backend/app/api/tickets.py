from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.common import require_employee
from app.dependencies import get_current_user, get_db, require_permission
from app.models.resolution import Resolution
from app.models.ticket import Ticket
from app.models.user import UserAccount
from app.schemas import Page
from app.schemas.knowledge import KnowledgeSearchHit
from app.schemas.sla import SLADetail
from app.schemas.ticket import (
    AssignRequest,
    EscalateRequest,
    MessageCreate,
    MessageOut,
    ReopenRequest,
    ResolveRequest,
    ResolutionOut,
    TicketCreate,
    TicketDetail,
    TicketEventOut,
    TicketOut,
)
from app.security.permissions import has_permission
from app.services.knowledge_service import knowledge_service
from app.services.sla_service import sla_service
from app.services.ticket_service import ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _detail(db: Session, ticket: Ticket, user: UserAccount) -> TicketDetail:
    can_see_internal = has_permission(user.role_names, "manage_tickets")
    base = TicketOut.model_validate(ticket).model_dump()
    messages = [m for m in ticket.messages if not m.is_deleted and (can_see_internal or not m.is_internal)]
    resolutions = db.query(Resolution).filter(Resolution.ticket_id == ticket.ticket_id).order_by(Resolution.resolved_at).all()
    return TicketDetail(
        **base,
        messages=[MessageOut.model_validate(m) for m in messages],
        events=[TicketEventOut.model_validate(e) for e in ticket.events] if can_see_internal else [],
        assignments=[a for a in ticket.assignments] if can_see_internal else [],
        escalations=[e for e in ticket.escalations] if can_see_internal else [],
        resolutions=[ResolutionOut.model_validate(r) for r in resolutions],
    )


@router.post("", response_model=TicketDetail, status_code=201)
def create_ticket(
    body: TicketCreate,
    user: UserAccount = Depends(require_permission("submit_ticket")),
    db: Session = Depends(get_db),
) -> TicketDetail:
    requester = require_employee(db, user)
    ticket = ticket_service.create_ticket(db, requester, body.subject, body.description, user, body.channel)
    db.commit()
    db.refresh(ticket)
    return _detail(db, ticket, user)


@router.get("", response_model=Page[TicketOut])
def list_tickets(
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    mine: bool = False,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[TicketOut]:
    items, total = ticket_service.list_tickets(db, user, status, category, priority, mine, search, skip, limit)
    return Page[TicketOut](items=[TicketOut.model_validate(t) for t in items], total=total, skip=skip, limit=limit)


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(ticket_id: str, user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)) -> TicketDetail:
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    return _detail(db, ticket, user)


@router.get("/{ticket_id}/messages", response_model=List[MessageOut])
def list_messages(ticket_id: str, user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)) -> List[MessageOut]:
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    return _detail(db, ticket, user).messages


@router.post("/{ticket_id}/messages", response_model=MessageOut, status_code=201)
def add_message(
    ticket_id: str, body: MessageCreate, user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)
) -> MessageOut:
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    message = ticket_service.add_message(db, ticket, user, body.body, body.is_internal)
    db.commit()
    return MessageOut.model_validate(message)


@router.get("/{ticket_id}/suggestions", response_model=List[KnowledgeSearchHit])
def suggestions(ticket_id: str, user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)) -> List[KnowledgeSearchHit]:
    from app.api.knowledge import to_hit
    from app.models.employee import Employee

    ticket = ticket_service.get_ticket(db, ticket_id, user)
    requester = db.query(Employee).filter(Employee.employee_id == ticket.requester_id).first()
    results = knowledge_service.search(
        db, "%s %s" % (ticket.subject, ticket.description), ticket.category_code, requester,
        ticket.created_at.date(), ticket.is_sensitive,
    )
    return [to_hit(r) for r in results]


@router.get("/{ticket_id}/sla", response_model=SLADetail)
def ticket_sla(ticket_id: str, user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)) -> SLADetail:
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    sla = sla_service.require(db, ticket.ticket_id)
    status = sla_service.evaluate(db, sla)
    from app.schemas.sla import SLAOut

    return SLADetail(
        **SLAOut.model_validate(sla).model_dump(),
        elapsed_hours=status.elapsed_hours, remaining_hours=status.remaining_hours,
        percent_consumed=status.percent_consumed, is_warning=status.is_warning,
    )


@router.post("/{ticket_id}/assign", response_model=TicketDetail)
def assign(
    ticket_id: str, body: AssignRequest,
    user: UserAccount = Depends(require_permission("manage_tickets")), db: Session = Depends(get_db),
) -> TicketDetail:
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    ticket_service.assign(db, ticket, user, body.team_id, body.assignee_user_id)
    db.commit()
    db.refresh(ticket)
    return _detail(db, ticket, user)


@router.post("/{ticket_id}/start", response_model=TicketDetail)
def start(ticket_id: str, user: UserAccount = Depends(require_permission("manage_tickets")), db: Session = Depends(get_db)) -> TicketDetail:
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    ticket_service.start_work(db, ticket, user)
    db.commit()
    db.refresh(ticket)
    return _detail(db, ticket, user)


@router.post("/{ticket_id}/escalate", response_model=TicketDetail)
def escalate(
    ticket_id: str, body: EscalateRequest,
    user: UserAccount = Depends(require_permission("escalate_ticket")), db: Session = Depends(get_db),
) -> TicketDetail:
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    ticket_service.escalate(db, ticket, user, body.reason, body.to_team_id)
    db.commit()
    db.refresh(ticket)
    return _detail(db, ticket, user)


@router.post("/{ticket_id}/resolve", response_model=TicketDetail)
def resolve(
    ticket_id: str, body: ResolveRequest,
    user: UserAccount = Depends(require_permission("resolve_tickets")), db: Session = Depends(get_db),
) -> TicketDetail:
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    ticket_service.resolve(
        db, ticket, user, body.resolution_type, body.summary, body.resolution_text,
        body.policy_version_id, body.article_id, body.citation_id,
    )
    db.commit()
    db.refresh(ticket)
    return _detail(db, ticket, user)


@router.post("/{ticket_id}/close", response_model=TicketDetail)
def close(ticket_id: str, user: UserAccount = Depends(require_permission("resolve_tickets")), db: Session = Depends(get_db)) -> TicketDetail:
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    ticket_service.close(db, ticket, user)
    db.commit()
    db.refresh(ticket)
    return _detail(db, ticket, user)


@router.post("/{ticket_id}/reopen", response_model=TicketDetail)
def reopen(ticket_id: str, body: ReopenRequest, user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)) -> TicketDetail:
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    ticket_service.reopen(db, ticket, user, body.reason)
    db.commit()
    db.refresh(ticket)
    return _detail(db, ticket, user)


@router.post("/{ticket_id}/cancel", response_model=TicketDetail)
def cancel(ticket_id: str, user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)) -> TicketDetail:
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    ticket_service.cancel(db, ticket, user)
    db.commit()
    db.refresh(ticket)
    return _detail(db, ticket, user)
