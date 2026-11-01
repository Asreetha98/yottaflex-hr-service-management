"""KPI calculations from database queries."""

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import CLASSIFIABLE_CATEGORIES, OPEN_STATUSES
from app.models.base import utcnow
from app.models.knowledge import Category
from app.models.resolution import Resolution
from app.models.sla import SLA
from app.models.ticket import Escalation, Ticket
from app.rules.sla_engine import BusinessHoursCalculator
from app.services.sla_service import sla_service


class AnalyticsService:
    def _tickets(self, db: Session, ticket_query: Optional[Any] = None):
        return ticket_query if ticket_query is not None else db.query(Ticket).filter(Ticket.is_deleted.is_(False))

    def _category_map(self, db: Session) -> Dict[str, str]:
        return {c.category_id: c.code for c in db.query(Category).all()}

    # ------------------------------------------------------------------ #
    def overview(self, db: Session, ticket_query: Optional[Any] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
        when = now or utcnow()
        query = self._tickets(db, ticket_query)
        tickets = query.all()
        ids = [t.ticket_id for t in tickets]
        total = len(tickets)
        open_count = sum(1 for t in tickets if t.status in OPEN_STATUSES)
        resolved = sum(1 for t in tickets if t.status in ("RESOLVED", "CLOSED"))
        sla = sla_service.metrics(db, when, ids) if ids else sla_service.metrics(db, when, ["__none__"])
        day_ago = when - timedelta(days=1)
        return {
            "total_tickets": total,
            "open_tickets": open_count,
            "resolved_tickets": resolved,
            "awaiting_clarification": sum(1 for t in tickets if t.status == "AWAITING_CLARIFICATION"),
            "escalated_tickets": sum(1 for t in tickets if t.status == "ESCALATED"),
            "sensitive_tickets": sum(1 for t in tickets if t.is_sensitive),
            "created_last_24h": sum(1 for t in tickets if t.created_at >= day_ago),
            "sla_compliance_rate": sla["compliance_rate"],
            "sla_breached": sla["breached"],
            "sla_warning": sla["warning"],
        }

    def tickets(self, db: Session, ticket_query: Optional[Any] = None) -> Dict[str, Any]:
        tickets = self._tickets(db, ticket_query).all()
        codes = self._category_map(db)
        by_status = Counter(t.status for t in tickets)
        by_priority = Counter(t.priority for t in tickets)
        by_category = Counter(codes.get(t.category_id, "UNCLASSIFIED") for t in tickets)
        by_channel = Counter(t.channel for t in tickets)
        by_day: Dict[str, int] = defaultdict(int)
        for t in tickets:
            by_day[t.created_at.date().isoformat()] += 1
        return {
            "total": len(tickets),
            "by_status": dict(sorted(by_status.items())),
            "by_priority": dict(sorted(by_priority.items())),
            "by_category": dict(sorted(by_category.items())),
            "by_channel": dict(sorted(by_channel.items())),
            "daily_volume": [{"date": d, "count": c} for d, c in sorted(by_day.items())][-30:],
            "ambiguous": sum(1 for t in tickets if t.is_ambiguous),
        }

    def performance(self, db: Session, ticket_query: Optional[Any] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
        when = now or utcnow()
        tickets = self._tickets(db, ticket_query).all()
        ids = [t.ticket_id for t in tickets]
        calc = BusinessHoursCalculator()

        resolution_hours: List[float] = []
        first_response_hours: List[float] = []
        for t in tickets:
            if t.resolved_at is not None:
                resolution_hours.append(calc.elapsed_business_hours(t.created_at, t.resolved_at))
            if t.first_response_at is not None:
                first_response_hours.append(calc.elapsed_business_hours(t.created_at, t.first_response_at))

        reopened = sum(1 for t in tickets if t.reopen_count > 0)
        ever_resolved = sum(1 for t in tickets if t.resolved_at is not None or t.reopen_count > 0)
        escalated = db.query(func.count(func.distinct(Escalation.ticket_id))).filter(
            Escalation.ticket_id.in_(ids or ["__none__"])).scalar() or 0
        scores = [
            r.satisfaction_score for r in db.query(Resolution)
            .filter(Resolution.ticket_id.in_(ids or ["__none__"]), Resolution.satisfaction_score.isnot(None)).all()
        ]
        sla = sla_service.metrics(db, when, ids or ["__none__"])

        def avg(values: List[float]) -> Optional[float]:
            return round(sum(values) / len(values), 2) if values else None

        return {
            "avg_resolution_business_hours": avg(resolution_hours),
            "avg_first_response_business_hours": avg(first_response_hours),
            "sla_compliance_rate": sla["compliance_rate"],
            "sla_by_policy": sla["by_policy"],
            "reopen_rate": round(reopened / ever_resolved, 4) if ever_resolved else None,
            "escalation_rate": round(escalated / len(tickets), 4) if tickets else None,
            "avg_satisfaction": avg([float(s) for s in scores]),
            "resolved_count": len(resolution_hours),
        }

    # ------------------------------------------------------------------ #
    def evaluation(self, db: Session, ground_truth_path: Optional[str] = None) -> Dict[str, Any]:
        """Compare stored ticket decisions with the generator's ground truth.

        Ground truth is produced independently of the engines (see ENGINEERING_DECISIONS ED-14).
        Returns ``available = False`` when no ground-truth file exists.
        """
        path = ground_truth_path or get_settings().ground_truth_path
        if not os.path.exists(path):
            return {"available": False, "reason": "Ground truth file not found: %s" % path,
                    "evaluated": 0, "category_accuracy": None, "sensitive_precision": None,
                    "sensitive_recall": None, "per_category": {}, "confusion": {}}
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        truth = {row["ticket_id"]: row for row in (data if isinstance(data, list) else data.get("tickets", []))}

        codes = self._category_map(db)
        tickets = db.query(Ticket).filter(Ticket.ticket_id.in_(list(truth) or ["__none__"])).all()
        correct = 0
        tp = fp = fn = tn = 0
        confusion: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        per_cat: Dict[str, Dict[str, int]] = {c: {"tp": 0, "fp": 0, "fn": 0} for c in CLASSIFIABLE_CATEGORIES}
        evaluated = 0
        for t in tickets:
            row = truth[t.ticket_id]
            expected = row.get("expected_category")
            predicted = codes.get(t.category_id, "GENERAL")
            if expected is None:
                continue
            evaluated += 1
            confusion[expected][predicted] += 1
            if expected == predicted:
                correct += 1
            for c in per_cat:
                if predicted == c and expected == c:
                    per_cat[c]["tp"] += 1
                elif predicted == c and expected != c:
                    per_cat[c]["fp"] += 1
                elif predicted != c and expected == c:
                    per_cat[c]["fn"] += 1
            expected_sensitive = bool(row.get("expected_sensitive"))
            if expected_sensitive and t.is_sensitive:
                tp += 1
            elif t.is_sensitive and not expected_sensitive:
                fp += 1
            elif expected_sensitive and not t.is_sensitive:
                fn += 1
            else:
                tn += 1

        def ratio(n: int, d: int) -> Optional[float]:
            return round(n / d, 4) if d else None

        return {
            "available": True,
            "evaluated": evaluated,
            "category_accuracy": ratio(correct, evaluated),
            "sensitive_precision": ratio(tp, tp + fp),
            "sensitive_recall": ratio(tp, tp + fn),
            "sensitive_counts": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            "per_category": {
                c: {"precision": ratio(v["tp"], v["tp"] + v["fp"]), "recall": ratio(v["tp"], v["tp"] + v["fn"])}
                for c, v in per_cat.items()
            },
            "confusion": {k: dict(v) for k, v in confusion.items()},
        }


analytics_service = AnalyticsService()
