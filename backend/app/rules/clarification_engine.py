"""Deterministic clarification workflow.

Decides whether a ticket needs more information before it can be routed and
produces the questions to ask. Required fields are detected by keyword / date
patterns, never by a language model.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from app.rules.classification_engine import (
    GENERAL,
    ClassificationResult,
    contains_term,
    normalize_text,
)

MIN_DESCRIPTION_WORDS = 5

MONTHS = (
    "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug",
    "sep", "sept", "oct", "nov", "dec",
)
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
RELATIVE_DATES = ("today", "tomorrow", "yesterday", "next week", "last week", "this week", "next month")

DATE_REGEX = re.compile(
    r"\b(?:\d{4}\s\d{1,2}\s\d{1,2}|\d{1,2}\s\d{1,2}\s\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s(?:%s)|(?:%s)\s\d{1,2}(?:st|nd|rd|th)?)\b"
    % ("|".join(MONTHS), "|".join(MONTHS))
)


@dataclass(frozen=True)
class ClarificationTemplate:
    category: str
    required_field: str
    question_text: str
    detection_keywords: Tuple[str, ...]
    display_order: int = 1
    detect_dates: bool = False


@dataclass
class ClarificationDecision:
    needs_clarification: bool
    reasons: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    questions: List[str] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "needs_clarification": self.needs_clarification,
            "reasons": list(self.reasons),
            "missing_fields": list(self.missing_fields),
            "questions": list(self.questions),
            "message": self.message,
        }


DEFAULT_TEMPLATES: Tuple[ClarificationTemplate, ...] = (
    ClarificationTemplate(
        "PAYROLL", "pay_period",
        "Which pay period or payslip month is affected?",
        ("pay period", "last month", "this month", "week", "payslip", "pay slip", "month") + MONTHS,
        1, True,
    ),
    ClarificationTemplate(
        "LEAVE", "leave_type",
        "Which type of leave is this about (annual, sick, parental, other)?",
        ("annual", "sick", "maternity", "paternity", "parental", "bereavement", "sabbatical",
         "pto", "vacation", "unpaid", "casual", "medical leave", "paid time off"),
        1,
    ),
    ClarificationTemplate(
        "LEAVE", "leave_dates",
        "What dates are you requesting or asking about?",
        ("tomorrow", "next week", "today", "yesterday", "this week", "last week") + MONTHS + WEEKDAYS,
        2, True,
    ),
    ClarificationTemplate(
        "BENEFITS", "plan_type",
        "Which benefit plan is this about (health, dental, vision, retirement, other)?",
        ("health", "dental", "vision", "401k", "retirement", "fsa", "hsa", "insurance",
         "wellness", "medical", "life insurance", "pension"),
        1,
    ),
    ClarificationTemplate(
        "ONBOARDING", "start_date",
        "What is your (or the new hire's) start date?",
        ("start date", "joining date", "date of joining", "first day") + MONTHS + WEEKDAYS,
        1, True,
    ),
)

GENERAL_TOPIC_QUESTION = (
    "Could you tell us what your request is about: payroll, leave, benefits or onboarding?"
)
MORE_DETAIL_QUESTION = "Could you add more detail about what you need help with?"


class ClarificationEngine:
    def __init__(self, templates: Optional[Iterable[ClarificationTemplate]] = None) -> None:
        self.templates: Tuple[ClarificationTemplate, ...] = (
            tuple(templates) if templates is not None else DEFAULT_TEMPLATES
        )

    # ------------------------------------------------------------------ #
    def get_clarification_template(
        self, category: str, missing_fields: Optional[Sequence[str]] = None
    ) -> List[ClarificationTemplate]:
        """Templates for ``category`` limited to ``missing_fields`` (all if ``None``)."""
        wanted = set(missing_fields) if missing_fields is not None else None
        selected = [
            t
            for t in self.templates
            if t.category == category and (wanted is None or t.required_field in wanted)
        ]
        return sorted(selected, key=lambda t: (t.display_order, t.required_field))

    def detect_missing_fields(self, category: str, subject: Optional[str], description: Optional[str]) -> List[str]:
        text = normalize_text("%s %s" % (subject or "", description or ""))
        missing: List[str] = []
        for template in self.get_clarification_template(category):
            present = any(contains_term(text, kw) for kw in template.detection_keywords)
            if not present and template.detect_dates:
                present = DATE_REGEX.search(text) is not None
            if not present:
                missing.append(template.required_field)
        return missing

    # ------------------------------------------------------------------ #
    def needs_clarification(
        self,
        subject: Optional[str],
        description: Optional[str],
        classification_result: ClassificationResult,
        is_sensitive: bool = False,
        already_clarified: bool = False,
    ) -> ClarificationDecision:
        """Apply rules C1-C4 from BUSINESS_RULES.md.

        Sensitive tickets are never put through clarification, and a ticket is
        clarified at most once automatically so it cannot loop.
        """
        if is_sensitive:
            return ClarificationDecision(False, message="Sensitive ticket: routed without clarification.")
        if already_clarified:
            return ClarificationDecision(False, message="Already clarified once; routing as-is.")

        reasons: List[str] = []
        missing: List[str] = []
        questions: List[str] = []
        category = classification_result.category

        if category == GENERAL:
            reasons.append("C1_LOW_CONFIDENCE")
            questions.append(GENERAL_TOPIC_QUESTION)
        elif classification_result.is_ambiguous and classification_result.alternative_categories:
            runner = classification_result.alternative_categories[0].category
            reasons.append("C2_AMBIGUOUS")
            questions.append(
                "Your request could relate to %s or %s. Which one is it about?" % (category, runner)
            )

        if category != GENERAL:
            fields = self.detect_missing_fields(category, subject, description)
            if fields:
                reasons.append("C3_MISSING_FIELDS")
                missing.extend(fields)
                questions.extend(t.question_text for t in self.get_clarification_template(category, fields))

        if len(normalize_text(description).split()) < MIN_DESCRIPTION_WORDS:
            reasons.append("C4_SHORT_DESCRIPTION")
            questions.append(MORE_DETAIL_QUESTION)

        if not reasons:
            return ClarificationDecision(False, message="Ticket has sufficient information.")

        message = "We need a little more information to route your request:\n" + "\n".join(
            "%d. %s" % (i, q) for i, q in enumerate(questions, start=1)
        )
        return ClarificationDecision(True, reasons, missing, questions, message)
