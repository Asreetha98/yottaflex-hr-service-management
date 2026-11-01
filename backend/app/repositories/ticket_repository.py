from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.ticket import Assignment, Escalation, Message, Ticket, TicketEvent
from app.repositories.base_repository import BaseRepository


class TicketRepository(BaseRepository[Ticket]):
    def __init__(self, db: Session) -> None:
        super().__init__(Ticket, db)

    def by_requester(self, employee_id: str, skip: int = 0, limit: int = 50) -> List[Ticket]:
        return self.list(skip, limit, [Ticket.requester_id == employee_id], Ticket.created_at.desc())

    def by_status(self, status: str, skip: int = 0, limit: int = 50) -> List[Ticket]:
        return self.list(skip, limit, [Ticket.status == status], Ticket.created_at.desc())

    def messages(self, ticket_id: str, include_internal: bool = False) -> List[Message]:
        query = self.db.query(Message).filter(Message.ticket_id == ticket_id, Message.is_deleted.is_(False))
        if not include_internal:
            query = query.filter(Message.is_internal.is_(False))
        return query.order_by(Message.sequence_number).all()

    def events(self, ticket_id: str) -> List[TicketEvent]:
        return (
            self.db.query(TicketEvent)
            .filter(TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.created_at, TicketEvent.event_id)
            .all()
        )

    def current_assignment(self, ticket_id: str) -> Optional[Assignment]:
        return (
            self.db.query(Assignment)
            .filter(Assignment.ticket_id == ticket_id, Assignment.is_current.is_(True))
            .first()
        )

    def escalations(self, ticket_id: str) -> List[Escalation]:
        return (
            self.db.query(Escalation)
            .filter(Escalation.ticket_id == ticket_id)
            .order_by(Escalation.escalated_at)
            .all()
        )
