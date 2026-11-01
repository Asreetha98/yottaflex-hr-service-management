"""Deterministic ticket routing.

Rules are evaluated in ``priority_order``; the first match wins. The result names
a *team type* (e.g. ``PAYROLL``) and support level; the service layer resolves it
to a concrete team row.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.rules.classification_engine import GENERAL, ClassificationResult
from app.rules.sensitive_routing_engine import SensitiveDetectionResult

FALLBACK_RULE_ID = "RRL-07"


@dataclass(frozen=True)
class RoutingRuleData:
    rule_id: str
    name: str
    priority_order: int
    target_team: str  # team type
    support_level: str = "L1"
    category: Optional[str] = None  # None = any category
    is_sensitive: Optional[bool] = None  # None = any, True = sensitive only, False = non-sensitive only
    is_active: bool = True

    def matches(self, category: str, sensitive: bool) -> bool:
        if not self.is_active:
            return False
        if self.is_sensitive is not None and self.is_sensitive != sensitive:
            return False
        if self.category is not None and self.category != category:
            return False
        return True


DEFAULT_ROUTING_RULES: Tuple[RoutingRuleData, ...] = (
    RoutingRuleData("RRL-01", "Sensitive cases to Employee Relations", 1, "EMPLOYEE_RELATIONS", "L2", None, True),
    RoutingRuleData("RRL-02", "Payroll queue", 2, "PAYROLL", "L1", "PAYROLL", False),
    RoutingRuleData("RRL-03", "Leave queue", 3, "LEAVE", "L1", "LEAVE", False),
    RoutingRuleData("RRL-04", "Benefits queue", 4, "BENEFITS", "L1", "BENEFITS", False),
    RoutingRuleData("RRL-05", "Onboarding queue", 5, "ONBOARDING", "L1", "ONBOARDING", False),
    RoutingRuleData("RRL-06", "IT operations queue", 6, "IT_OPS", "L1", "IT", False),
    RoutingRuleData("RRL-07", "Fallback to HR general", 7, "HR_GENERAL", "L1", None, None),
)


@dataclass
class RoutingDecision:
    assigned_team: str
    routing_reason: str
    rule_reference: str
    support_level: str = "L1"
    escalate_immediately: bool = False
    is_restricted: bool = False
    evaluated_rules: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assigned_team": self.assigned_team,
            "routing_reason": self.routing_reason,
            "rule_reference": self.rule_reference,
            "support_level": self.support_level,
            "escalate_immediately": self.escalate_immediately,
            "is_restricted": self.is_restricted,
            "evaluated_rules": list(self.evaluated_rules),
        }


class RoutingEngine:
    def __init__(self, rules: Optional[Iterable[RoutingRuleData]] = None) -> None:
        loaded = tuple(rules) if rules is not None else DEFAULT_ROUTING_RULES
        self.rules: Tuple[RoutingRuleData, ...] = tuple(sorted(loaded, key=lambda r: (r.priority_order, r.rule_id)))

    def determine_assignment(
        self,
        ticket: Any,
        classification_result: ClassificationResult,
        sensitivity_result: SensitiveDetectionResult,
    ) -> RoutingDecision:
        """Pick the team for a ticket. ``ticket`` is only used for the reason text."""
        category = classification_result.category
        sensitive = sensitivity_result.is_sensitive
        ticket_id = getattr(ticket, "ticket_id", None)

        evaluated: List[str] = []
        for rule in self.rules:
            evaluated.append(rule.rule_id)
            if rule.matches(category, sensitive):
                return RoutingDecision(
                    assigned_team=rule.target_team,
                    routing_reason=self._reason(rule, category, classification_result.confidence, sensitivity_result, ticket_id),
                    rule_reference=rule.rule_id,
                    support_level=rule.support_level,
                    escalate_immediately=sensitive,
                    is_restricted=sensitive,
                    evaluated_rules=evaluated,
                )

        # No rule matched (e.g. every rule disabled): hard-coded safe default.
        return RoutingDecision(
            assigned_team="HR_GENERAL",
            routing_reason="No active routing rule matched; defaulted to HR_GENERAL.",
            rule_reference=FALLBACK_RULE_ID,
            support_level="L1",
            escalate_immediately=sensitive,
            is_restricted=sensitive,
            evaluated_rules=evaluated,
        )

    @staticmethod
    def _reason(
        rule: RoutingRuleData,
        category: str,
        confidence: float,
        sensitivity: SensitiveDetectionResult,
        ticket_id: Optional[str],
    ) -> str:
        prefix = "Ticket %s: " % ticket_id if ticket_id else ""
        if sensitivity.is_sensitive:
            return "%sSensitive case (%s) routed to %s %s by %s."  % (
                prefix, ", ".join(sensitivity.matched_patterns), rule.target_team, rule.support_level, rule.rule_id,
            )
        if category == GENERAL:
            return "%sCategory GENERAL (confidence %.2f) routed to %s by %s." % (
                prefix, confidence, rule.target_team, rule.rule_id,
            )
        return "%sCategory %s with confidence %.2f routed to %s by %s." % (
            prefix, category, confidence, rule.target_team, rule.rule_id,
        )
