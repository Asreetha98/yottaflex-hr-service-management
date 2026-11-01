"""Ticket lifecycle orchestration.

create -> classify -> (clarify | route/assign) -> in progress -> resolve -> close,
plus escalate / reopen / cancel. Every transition is validated against
``ALLOWED_TRANSITIONS`` and written to ``ticket_events`` and ``audit_logs``.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import ALLOWED_TRANSITIONS, OPEN_STATUSES
from app.exceptions import BusinessRuleError, ForbiddenError, NotFoundError
from app.models.base import utcnow
from app.models.employee import Employee, Team
from app.models.knowledge import Category
from app.models.resolution import Resolution
from app.models.rules import CategoryRule, ClarificationTemplate as ClarificationTemplateRow, RoutingRule
from app.models.ticket import Assignment, Escalation, Message, Ticket
from app.models.user import UserAccount
from app.rules.clarification_engine import (
    ClarificationDecision,
    ClarificationEngine,
    ClarificationTemplate,
)
from app.rules.classification_engine import (
    ClassificationEngine,
    ClassificationResult,
    build_rules_from_entries,
)
from app.rules.routing_engine import RoutingEngine, RoutingRuleData
from app.rules.sensitive_routing_engine import SensitiveDetectionResult, SensitiveRoutingEngine
from app.rules.sla_engine import derive_priority
from app.security.permissions import (
    can_manage_category,
    can_view_sensitive,
    has_permission,
    is_admin,
)
from app.services.audit_service import AuditService
from app.services.events import record_ticket_event
from app.services.ids import next_id
from app.services.sla_service import sla_service

audit = AuditService()
GENERAL = "GENERAL"


class TicketService:
    # ------------------------------------------------------------------ #
    # Engine factories (rules stored as data when present, defaults otherwise)
    # ------------------------------------------------------------------ #
    def classification_engine(self, db: Session) -> ClassificationEngine:
        settings = get_settings()
        rows = (
            db.query(Category.code, CategoryRule.rule_type, CategoryRule.term, CategoryRule.weight)
            .join(Category, Category.category_id == CategoryRule.category_id)
            .filter(CategoryRule.is_active.is_(True), CategoryRule.is_deleted.is_(False))
            .order_by(CategoryRule.rule_id)
            .all()
        )
        rules = build_rules_from_entries([tuple(r) for r in rows]) if rows else None
        return ClassificationEngine(
            rules,
            confidence_threshold=settings.classification_confidence_threshold,
            ambiguity_margin=settings.ambiguity_margin,
        )

    def clarification_engine(self, db: Session) -> ClarificationEngine:
        rows = (
            db.query(ClarificationTemplateRow, Category.code)
            .join(Category, Category.category_id == ClarificationTemplateRow.category_id)
            .filter(ClarificationTemplateRow.is_active.is_(True), ClarificationTemplateRow.is_deleted.is_(False))
            .all()
        )
        if not rows:
            return ClarificationEngine()
        templates = [
            ClarificationTemplate(
                code, t.required_field, t.question_text, tuple(t.detection_keywords or ()),
                t.display_order, detect_dates=t.required_field in ("pay_period", "leave_dates", "start_date"),
            )
            for t, code in rows
        ]
        return ClarificationEngine(templates)

    def routing_engine(self, db: Session) -> RoutingEngine:
        rows = (
            db.query(RoutingRule, Team, Category)
            .join(Team, Team.team_id == RoutingRule.target_team_id)
            .outerjoin(Category, Category.category_id == RoutingRule.category_id)
            .filter(RoutingRule.is_active.is_(True), RoutingRule.is_deleted.is_(False))
            .all()
        )
        if not rows:
            return RoutingEngine()
        return RoutingEngine([
            RoutingRuleData(
                r.rule_id, r.name, r.priority_order, t.team_type, t.support_level,
                c.code if c else None, r.is_sensitive,
            )
            for r, t, c in rows
        ])

    # ------------------------------------------------------------------ #
    # Access control
    # ------------------------------------------------------------------ #
    def can_view(self, db: Session, user: UserAccount, ticket: Ticket) -> bool:
        roles = user.role_names
        is_requester = user.employee_id is not None and ticket.requester_id == user.employee_id
        if ticket.is_sensitive or ticket.access_level == "RESTRICTED":
            return is_requester or can_view_sensitive(roles, user.can_view_sensitive)
        if is_requester and has_permission(roles, "view_own_tickets"):
            return True
        if has_permission(roles, "view_all_tickets"):
            if "IT_OPS" in roles and not (set(roles) & {"ADMIN", "HR_PARTNER"}):
                return ticket.category is not None and ticket.category.code == "IT"
            return True
        if has_permission(roles, "view_team_tickets") and user.employee_id:
            requester = db.query(Employee).filter(Employee.employee_id == ticket.requester_id).first()
            return requester is not None and requester.manager_id == user.employee_id
        return False

    def get_ticket(self, db: Session, ticket_id: str, user: Optional[UserAccount] = None) -> Ticket:
        ticket = (
            db.query(Ticket)
            .filter(Ticket.ticket_id == ticket_id, Ticket.is_deleted.is_(False))
            .first()
        )
        # Existence of restricted / inaccessible tickets is not disclosed: always 404.
        if ticket is None or (user is not None and not self.can_view(db, user, ticket)):
            if ticket is not None and user is not None:
                audit.record(db, "TICKET_ACCESS_DENIED", "ACCESS_DENIED", "tickets", ticket_id, user)
                db.commit()
            raise NotFoundError("Ticket %s not found" % ticket_id)
        return ticket

    def visible_query(self, db: Session, user: UserAccount):
        """Query of tickets the user may see (mirrors ``can_view``)."""
        roles = user.role_names
        query = db.query(Ticket).filter(Ticket.is_deleted.is_(False))
        sensitive_ok = can_view_sensitive(roles, user.can_view_sensitive)
        conditions = []
        own = Ticket.requester_id == user.employee_id if user.employee_id else None
        if own is not None:
            conditions.append(own)  # requester always sees own tickets (incl. restricted)
        standard = Ticket.access_level == "STANDARD"
        if has_permission(roles, "view_all_tickets"):
            if "IT_OPS" in roles and not (set(roles) & {"ADMIN", "HR_PARTNER"}):
                it_ids = db.query(Category.category_id).filter(Category.code == "IT")
                conditions.append((standard) & Ticket.category_id.in_(it_ids))
            else:
                conditions.append(standard)
        elif has_permission(roles, "view_team_tickets") and user.employee_id:
            reports = db.query(Employee.employee_id).filter(Employee.manager_id == user.employee_id)
            conditions.append(standard & Ticket.requester_id.in_(reports))
        if sensitive_ok:
            conditions.append(Ticket.access_level == "RESTRICTED")
        if not conditions:
            return query.filter(Ticket.ticket_id == "__none__")
        return query.filter(or_(*conditions))

    # ------------------------------------------------------------------ #
    # State machine
    # ------------------------------------------------------------------ #
    @staticmethod
    def assert_transition(current: str, target: str) -> None:
        if target not in ALLOWED_TRANSITIONS.get(current, ()):
            raise BusinessRuleError(
                "Invalid status transition %s -> %s" % (current, target), "INVALID_TRANSITION"
            )

    def transition(
        self, db: Session, ticket: Ticket, target: str, actor: Optional[UserAccount] = None,
        event_type: str = "STATUS_CHANGED", details: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> Ticket:
        self.assert_transition(ticket.status, target)
        previous = ticket.status
        when = now or utcnow()
        ticket.status = target
        if target == "RESOLVED":
            ticket.resolved_at = when
        elif target == "CLOSED":
            ticket.closed_at = when
        elif target == "REOPENED":
            ticket.reopen_count += 1
            ticket.resolved_at = None
            ticket.closed_at = None
        db.flush()
        record_ticket_event(
            db, ticket.ticket_id, event_type, previous, target,
            actor.user_id if actor else None, details, when,
        )
        audit.record(
            db, "TICKET_%s" % target, "TRANSITION", "tickets", ticket.ticket_id, actor,
            old_values={"status": previous}, new_values={"status": target}, created_at=when,
        )
        return ticket

    # ------------------------------------------------------------------ #
    # Create + automated pipeline
    # ------------------------------------------------------------------ #
    def create_ticket(
        self, db: Session, requester: Employee, subject: str, description: str,
        actor: Optional[UserAccount] = None, channel: str = "PORTAL", now: Optional[datetime] = None,
    ) -> Ticket:
        when = now or utcnow()
        ticket = Ticket(
            ticket_id=next_id(db, Ticket.ticket_id, "TKT-2026-", 6),
            requester_id=requester.employee_id,
            subject=subject.strip(),
            description=description.strip(),
            status="NEW",
            channel=channel,
            created_at=when,
            updated_at=when,
        )
        db.add(ticket)
        db.flush()
        record_ticket_event(db, ticket.ticket_id, "CREATED", None, "NEW",
                            actor.user_id if actor else None, {"channel": channel}, when)
        audit.record(db, "TICKET_CREATED", "CREATE", "tickets", ticket.ticket_id, actor,
                     new_values={"subject": ticket.subject, "requester_id": requester.employee_id},
                     created_at=when)
        self.process_new_ticket(db, ticket, actor, when)
        return ticket

    def process_new_ticket(self, db: Session, ticket: Ticket, actor: Optional[UserAccount], now: datetime) -> None:
        classification = self.classify(db, ticket, actor, now)
        sensitivity = self._detect_sensitive(ticket)
        self._apply_classification(db, ticket, classification, sensitivity, actor, now)

        decision = self.clarification_engine(db).needs_clarification(
            ticket.subject, ticket.description, classification, sensitivity.is_sensitive
        )
        category_code = classification.category
        if sensitivity.is_sensitive:
            self._route(db, ticket, classification, sensitivity, actor, now)
            return
        # SLA starts at creation even when clarification is pending.
        sla_service.create_sla(db, ticket, category_code, ticket.priority, False, None, ticket.created_at)
        if decision.needs_clarification:
            self._request_clarification(db, ticket, decision, actor, now)
        else:
            self._route(db, ticket, classification, sensitivity, actor, now)

    def classify(self, db: Session, ticket: Ticket, actor: Optional[UserAccount], now: datetime,
                 extra_text: str = "") -> ClassificationResult:
        engine = self.classification_engine(db)
        return engine.classify(ticket.subject, (ticket.description + " " + extra_text).strip())

    @staticmethod
    def _detect_sensitive(ticket: Ticket, extra_text: str = "") -> SensitiveDetectionResult:
        return SensitiveRoutingEngine().detect(ticket.subject, (ticket.description + " " + extra_text).strip())

    def _apply_classification(
        self, db: Session, ticket: Ticket, result: ClassificationResult,
        sensitivity: SensitiveDetectionResult, actor: Optional[UserAccount], now: datetime,
    ) -> None:
        category = db.query(Category).filter(Category.code == result.category).first()
        ticket.category_id = category.category_id if category else None
        ticket.classification_confidence = result.confidence
        ticket.classification_explanation = result.to_dict()
        ticket.is_ambiguous = result.is_ambiguous
        ticket.is_sensitive = sensitivity.is_sensitive
        ticket.access_level = sensitivity.access_level
        ticket.sensitive_patterns = sensitivity.matched_patterns or None
        ticket.priority = derive_priority(ticket.subject, ticket.description, sensitivity.is_sensitive)
        db.flush()
        self.transition(db, ticket, "CLASSIFIED", actor, "CLASSIFIED",
                        {"category": result.category, "confidence": result.confidence,
                         "sensitive": sensitivity.is_sensitive, "explanation": result.decision_explanation},
                        now)

    def _request_clarification(self, db: Session, ticket: Ticket, decision: ClarificationDecision,
                               actor: Optional[UserAccount], now: datetime) -> None:
        self.transition(db, ticket, "AWAITING_CLARIFICATION", actor, "CLARIFICATION_REQUESTED",
                        {"reasons": decision.reasons, "missing_fields": decision.missing_fields}, now)
        self._add_message(db, ticket, None, "SYSTEM", "CLARIFICATION_REQUEST", decision.message, False, now)
        sla_service.pause(db, ticket, "AWAITING_CLARIFICATION", None, now)

    def _team_for(self, db: Session, team_type: str, level: str) -> Optional[Team]:
        query = db.query(Team).filter(Team.team_type == team_type, Team.is_deleted.is_(False),
                                      Team.is_active.is_(True))
        return query.filter(Team.support_level == level).order_by(Team.team_id).first() or \
            query.order_by(Team.team_id).first()

    def _route(self, db: Session, ticket: Ticket, classification: ClassificationResult,
               sensitivity: SensitiveDetectionResult, actor: Optional[UserAccount], now: datetime,
               assignment_type: str = "AUTO") -> Assignment:
        decision = self.routing_engine(db).determine_assignment(ticket, classification, sensitivity)
        team = self._team_for(db, decision.assigned_team, decision.support_level)
        if team is None:
            raise BusinessRuleError("No active team of type %s" % decision.assigned_team, "NO_TEAM")
        assignment = self._assign(db, ticket, team, decision.routing_reason, decision.rule_reference,
                                  assignment_type, actor, now)
        if ticket.status != "ASSIGNED":
            self.transition(db, ticket, "ASSIGNED", actor, "ASSIGNED",
                            {"team_id": team.team_id, "rule": decision.rule_reference}, now)
        sla_service.create_sla(db, ticket, classification.category, ticket.priority,
                               sensitivity.is_sensitive, decision.assigned_team, ticket.created_at)
        if decision.escalate_immediately:
            self._escalate(db, ticket, team, team, "SENSITIVE_CASE",
                           "Sensitive case detected: " + ", ".join(sensitivity.matched_patterns),
                           None, now, "L2", record_assignment=False)
        return assignment

    def _assign(self, db: Session, ticket: Ticket, team: Team, reason: str, rule: Optional[str],
                assignment_type: str, actor: Optional[UserAccount], now: datetime,
                user_id: Optional[str] = None) -> Assignment:
        for current in db.query(Assignment).filter(Assignment.ticket_id == ticket.ticket_id,
                                                   Assignment.is_current.is_(True)).all():
            current.is_current = False
            current.unassigned_at = now
        assignment = Assignment(
            assignment_id=next_id(db, Assignment.assignment_id, "ASG-", 6),
            ticket_id=ticket.ticket_id, team_id=team.team_id, assigned_user_id=user_id,
            assigned_by=actor.user_id if actor else None, assignment_type=assignment_type,
            routing_reason=reason, rule_reference=rule, is_current=True,
            assigned_at=now, created_at=now,
        )
        db.add(assignment)
        ticket.assigned_team_id = team.team_id
        ticket.assigned_user_id = user_id
        db.flush()
        return assignment

    # ------------------------------------------------------------------ #
    # Messages
    # ------------------------------------------------------------------ #
    def _add_message(self, db: Session, ticket: Ticket, sender: Optional[UserAccount], sender_type: str,
                     message_type: str, body: str, is_internal: bool, now: datetime) -> Message:
        sequence = (db.query(Message).filter(Message.ticket_id == ticket.ticket_id).count()) + 1
        message = Message(
            message_id="MSG-%s-%03d" % (ticket.ticket_id, sequence), ticket_id=ticket.ticket_id,
            sequence_number=sequence, sender_user_id=sender.user_id if sender else None,
            sender_type=sender_type, message_type=message_type, is_internal=is_internal,
            body=body.strip(), created_at=now, updated_at=now,
        )
        db.add(message)
        db.flush()
        return message

    def add_message(self, db: Session, ticket: Ticket, user: UserAccount, body: str,
                    is_internal: bool = False, now: Optional[datetime] = None) -> Message:
        when = now or utcnow()
        roles = user.role_names
        is_requester = user.employee_id == ticket.requester_id
        if not has_permission(roles, "send_message"):
            raise ForbiddenError("Missing permission: send_message")
        if ticket.status in ("CLOSED", "CANCELLED"):
            raise BusinessRuleError("Cannot message a %s ticket" % ticket.status, "TICKET_TERMINAL")
        if is_internal and is_requester and not has_permission(roles, "manage_tickets"):
            raise ForbiddenError("Requesters cannot add internal notes")

        sender_type = "EMPLOYEE" if (is_requester and not has_permission(roles, "manage_tickets")) else "AGENT"
        if ticket.status == "AWAITING_CLARIFICATION" and sender_type == "EMPLOYEE":
            message = self._add_message(db, ticket, user, sender_type, "CLARIFICATION_RESPONSE", body, False, when)
            record_ticket_event(db, ticket.ticket_id, "CLARIFICATION_RECEIVED", actor_user_id=user.user_id,
                                created_at=when)
            self._after_clarification(db, ticket, user, body, when)
            return message

        message_type = "INTERNAL_NOTE" if is_internal else "PUBLIC"
        message = self._add_message(db, ticket, user, sender_type, message_type, body, is_internal, when)
        record_ticket_event(db, ticket.ticket_id, "MESSAGE_ADDED", actor_user_id=user.user_id,
                            details={"internal": is_internal}, created_at=when)
        if sender_type == "AGENT" and not is_internal and ticket.first_response_at is None:
            sla_service.record_first_response(db, ticket, when)
        return message

    def _after_clarification(self, db: Session, ticket: Ticket, user: UserAccount, reply: str, now: datetime) -> None:
        sla_service.resume(db, ticket, user.user_id, now)
        classification = self.classify(db, ticket, user, now, reply)
        sensitivity = self._detect_sensitive(ticket, reply)
        category = db.query(Category).filter(Category.code == classification.category).first()
        ticket.category_id = category.category_id if category else ticket.category_id
        ticket.classification_confidence = classification.confidence
        ticket.classification_explanation = classification.to_dict()
        ticket.is_ambiguous = classification.is_ambiguous
        if sensitivity.is_sensitive:
            ticket.is_sensitive = True
            ticket.access_level = sensitivity.access_level
            ticket.sensitive_patterns = sensitivity.matched_patterns
            ticket.priority = "P1"
        self._route(db, ticket, classification, sensitivity, user, now)

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def assign(self, db: Session, ticket: Ticket, actor: UserAccount, team_id: Optional[str] = None,
               assignee_user_id: Optional[str] = None, now: Optional[datetime] = None) -> Ticket:
        when = now or utcnow()
        self._require_manage(ticket, actor)
        if ticket.status not in ("CLASSIFIED", "AWAITING_CLARIFICATION", "ASSIGNED", "IN_PROGRESS", "ESCALATED", "REOPENED"):
            raise BusinessRuleError("Cannot assign a %s ticket" % ticket.status, "INVALID_STATE")
        team = db.query(Team).filter(Team.team_id == (team_id or ticket.assigned_team_id)).first()
        if team is None:
            raise NotFoundError("Team not found")
        if team.is_restricted and not can_view_sensitive(actor.role_names, actor.can_view_sensitive):
            raise ForbiddenError("Restricted team")
        if assignee_user_id and not db.query(UserAccount).filter(UserAccount.user_id == assignee_user_id).first():
            raise NotFoundError("Assignee not found")
        self._assign(db, ticket, team, "Manually assigned by %s" % actor.username, None,
                     "MANUAL" if not ticket.assignments else "REASSIGNMENT", actor, when, assignee_user_id)
        if ticket.status in ("CLASSIFIED", "AWAITING_CLARIFICATION"):
            if ticket.status == "AWAITING_CLARIFICATION":
                sla_service.resume(db, ticket, actor.user_id, when)
            self.transition(db, ticket, "ASSIGNED", actor, "ASSIGNED", {"team_id": team.team_id}, when)
        else:
            record_ticket_event(db, ticket.ticket_id, "ASSIGNED", actor_user_id=actor.user_id,
                                details={"team_id": team.team_id, "assignee": assignee_user_id}, created_at=when)
        audit.record(db, "TICKET_ASSIGNED", "UPDATE", "tickets", ticket.ticket_id, actor,
                     new_values={"team_id": team.team_id, "assignee": assignee_user_id}, created_at=when)
        return ticket

    def start_work(self, db: Session, ticket: Ticket, actor: UserAccount, now: Optional[datetime] = None) -> Ticket:
        when = now or utcnow()
        self._require_manage(ticket, actor)
        self.transition(db, ticket, "IN_PROGRESS", actor, now=when)
        if ticket.first_response_at is None:
            sla_service.record_first_response(db, ticket, when)
        return ticket

    def escalate(self, db: Session, ticket: Ticket, actor: UserAccount, reason: str,
                 to_team_id: Optional[str] = None, now: Optional[datetime] = None) -> Ticket:
        when = now or utcnow()
        if not has_permission(actor.role_names, "escalate_ticket"):
            raise ForbiddenError("Missing permission: escalate_ticket")
        if ticket.status not in OPEN_STATUSES:
            raise BusinessRuleError("Cannot escalate a %s ticket" % ticket.status, "INVALID_STATE")
        to_team = db.query(Team).filter(Team.team_id == to_team_id).first() if to_team_id else \
            self._team_for(db, "HR_GENERAL", "L2")
        if to_team is None:
            raise NotFoundError("Escalation team not found")
        from_team = db.query(Team).filter(Team.team_id == ticket.assigned_team_id).first()
        self._escalate(db, ticket, from_team, to_team, "MANUAL", reason, actor, when, "L2")
        return ticket

    def _escalate(self, db: Session, ticket: Ticket, from_team: Optional[Team], to_team: Team,
                  reason_code: str, reason: str, actor: Optional[UserAccount], now: datetime,
                  level: str, record_assignment: bool = True) -> Escalation:
        escalation = Escalation(
            escalation_id=next_id(db, Escalation.escalation_id, "ESC-", 6), ticket_id=ticket.ticket_id,
            from_team_id=from_team.team_id if from_team else None, to_team_id=to_team.team_id,
            escalation_level=level, reason_code=reason_code, reason=reason,
            escalated_by=actor.user_id if actor else None, escalated_at=now, status="OPEN",
            created_at=now, updated_at=now,
        )
        db.add(escalation)
        db.flush()
        if record_assignment:
            self._assign(db, ticket, to_team, "Escalated: " + reason, None, "ESCALATION", actor, now)
        self.transition(db, ticket, "ESCALATED", actor, "ESCALATED",
                        {"reason_code": reason_code, "to_team": to_team.team_id, "level": level}, now)
        return escalation

    def resolve(self, db: Session, ticket: Ticket, actor: UserAccount, resolution_type: str, summary: str,
                resolution_text: str, policy_version_id: Optional[str] = None, article_id: Optional[str] = None,
                citation_id: Optional[str] = None, now: Optional[datetime] = None) -> Resolution:
        when = now or utcnow()
        if not has_permission(actor.role_names, "resolve_tickets"):
            raise ForbiddenError("Missing permission: resolve_tickets")
        self._require_manage(ticket, actor)
        if ticket.status != "IN_PROGRESS":
            raise BusinessRuleError("Only IN_PROGRESS tickets can be resolved", "INVALID_STATE")
        if resolution_type == "POLICY_ANSWER" and not (policy_version_id or article_id):
            raise BusinessRuleError("A policy answer must cite a policy version or knowledge article",
                                    "POLICY_SOURCE_REQUIRED")
        if policy_version_id:
            self._validate_policy_for_ticket(db, ticket, policy_version_id)
        count = db.query(Resolution).filter(Resolution.ticket_id == ticket.ticket_id).count()
        resolution = Resolution(
            resolution_id="RES-%s-%02d" % (ticket.ticket_id, count + 1), ticket_id=ticket.ticket_id,
            resolution_type=resolution_type, summary=summary[:500], resolution_text=resolution_text,
            policy_version_id=policy_version_id, citation_id=citation_id, article_id=article_id,
            resolved_by=actor.user_id, resolved_at=when, created_at=when, updated_at=when,
        )
        db.add(resolution)
        db.flush()
        self.transition(db, ticket, "RESOLVED", actor, "RESOLVED", {"resolution_id": resolution.resolution_id}, when)
        sla_service.mark_resolved(db, ticket, when)
        return resolution

    def _validate_policy_for_ticket(self, db: Session, ticket: Ticket, version_id: str) -> None:
        """A cited policy version must have been in force on the ticket creation date."""
        from app.models.policy import PolicyVersion
        from app.services.policy_service import policy_service

        version = db.query(PolicyVersion).filter(PolicyVersion.version_id == version_id).first()
        if version is None:
            raise NotFoundError("Policy version %s not found" % version_id)
        requester = db.query(Employee).filter(Employee.employee_id == ticket.requester_id).first()
        verdict = policy_service.effective_version(db, version.policy_id, ticket.created_at.date(), requester)
        if verdict.version is None or verdict.version.version_id != version_id:
            raise BusinessRuleError(
                "Policy version %s was not in force on %s (%s)" % (
                    version_id, ticket.created_at.date(), verdict.explanation),
                "POLICY_VERSION_NOT_EFFECTIVE",
            )

    def close(self, db: Session, ticket: Ticket, actor: UserAccount, now: Optional[datetime] = None) -> Ticket:
        self._require_manage(ticket, actor)
        return self.transition(db, ticket, "CLOSED", actor, "CLOSED", now=now)

    def reopen(self, db: Session, ticket: Ticket, actor: UserAccount, reason: str,
               now: Optional[datetime] = None) -> Ticket:
        when = now or utcnow()
        is_requester = actor.employee_id == ticket.requester_id
        if not (is_requester or has_permission(actor.role_names, "manage_tickets")):
            raise ForbiddenError("Only the requester or an agent can reopen a ticket")
        self.transition(db, ticket, "REOPENED", actor, "REOPENED", {"reason": reason}, when)
        last = (db.query(Resolution).filter(Resolution.ticket_id == ticket.ticket_id)
                .order_by(Resolution.resolved_at.desc()).first())
        if last is not None:
            last.was_reopened = True
        sla_service.reopen(db, ticket)
        if ticket.reopen_count >= 2:
            to_team = self._team_for(db, "HR_GENERAL", "L2")
            from_team = db.query(Team).filter(Team.team_id == ticket.assigned_team_id).first()
            if to_team is not None:
                self._escalate(db, ticket, from_team, to_team, "REOPEN_LIMIT",
                               "Ticket reopened %d times" % ticket.reopen_count, None, when, "L2")
        return ticket

    def cancel(self, db: Session, ticket: Ticket, actor: UserAccount, now: Optional[datetime] = None) -> Ticket:
        is_requester = actor.employee_id == ticket.requester_id
        if not (is_requester or has_permission(actor.role_names, "manage_tickets")):
            raise ForbiddenError("Not allowed to cancel this ticket")
        return self.transition(db, ticket, "CANCELLED", actor, "CANCELLED", now=now)

    def _require_manage(self, ticket: Ticket, actor: UserAccount) -> None:
        if not has_permission(actor.role_names, "manage_tickets"):
            raise ForbiddenError("Missing permission: manage_tickets")
        code = ticket.category.code if ticket.category else None
        if not can_manage_category(actor.role_names, code):
            raise ForbiddenError("Not permitted to manage %s tickets" % (code or "unclassified"))
        if ticket.is_sensitive and not can_view_sensitive(actor.role_names, actor.can_view_sensitive):
            raise ForbiddenError("Sensitive ticket: authorisation required")

    # ------------------------------------------------------------------ #
    # Listing
    # ------------------------------------------------------------------ #
    def list_tickets(self, db: Session, user: UserAccount, status: Optional[str] = None,
                     category_code: Optional[str] = None, priority: Optional[str] = None,
                     mine: bool = False, search: Optional[str] = None, skip: int = 0, limit: int = 50
                     ) -> Tuple[List[Ticket], int]:
        query = self.visible_query(db, user)
        if mine and user.employee_id:
            query = query.filter(Ticket.requester_id == user.employee_id)
        if status:
            query = query.filter(Ticket.status == status)
        if priority:
            query = query.filter(Ticket.priority == priority)
        if category_code:
            query = query.join(Category, Category.category_id == Ticket.category_id).filter(Category.code == category_code)
        if search:
            like = "%%%s%%" % search.strip()
            query = query.filter(or_(Ticket.subject.ilike(like), Ticket.ticket_id.ilike(like)))
        total = query.count()
        items = query.order_by(Ticket.created_at.desc(), Ticket.ticket_id.desc()).offset(skip).limit(limit).all()
        return items, total


ticket_service = TicketService()
