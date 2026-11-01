from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_permission
from app.models.user import UserAccount
from app.schemas.analytics import EvaluationMetrics, OverviewMetrics, PerformanceMetrics, TicketMetrics
from app.security.permissions import has_permission
from app.services.analytics_service import analytics_service
from app.services.ticket_service import ticket_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _scope(db: Session, user: UserAccount):
    """Analytics are computed only over tickets the caller may see."""
    return ticket_service.visible_query(db, user)


@router.get("/overview", response_model=OverviewMetrics)
def overview(user: UserAccount = Depends(require_permission("view_analytics")), db: Session = Depends(get_db)) -> OverviewMetrics:
    return OverviewMetrics(**analytics_service.overview(db, _scope(db, user)))


@router.get("/tickets", response_model=TicketMetrics)
def tickets(user: UserAccount = Depends(require_permission("view_analytics")), db: Session = Depends(get_db)) -> TicketMetrics:
    return TicketMetrics(**analytics_service.tickets(db, _scope(db, user)))


@router.get("/performance", response_model=PerformanceMetrics)
def performance(user: UserAccount = Depends(require_permission("view_analytics")), db: Session = Depends(get_db)) -> PerformanceMetrics:
    return PerformanceMetrics(**analytics_service.performance(db, _scope(db, user)))


@router.get("/evaluation", response_model=EvaluationMetrics)
def evaluation(_user: UserAccount = Depends(require_permission("manage_config")), db: Session = Depends(get_db)) -> EvaluationMetrics:
    return EvaluationMetrics(**analytics_service.evaluation(db))


@router.get("/my-summary", response_model=OverviewMetrics)
def my_summary(user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)) -> OverviewMetrics:
    """Counts over the caller's own tickets (available to every role)."""
    from app.models.ticket import Ticket

    query = db.query(Ticket).filter(Ticket.is_deleted.is_(False), Ticket.requester_id == user.employee_id)
    return OverviewMetrics(**analytics_service.overview(db, query))
