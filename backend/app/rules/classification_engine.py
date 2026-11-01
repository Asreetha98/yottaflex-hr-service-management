"""Deterministic ticket classification.

Scores a ticket against configurable keyword / phrase / synonym rule sets and
returns the winning category together with a full explanation. There is no
randomness, no learned model and no I/O: identical input always yields identical
output.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

GENERAL = "GENERAL"
CATEGORY_ORDER: Tuple[str, ...] = ("PAYROLL", "LEAVE", "BENEFITS", "ONBOARDING")

KEYWORD = "KEYWORD"
PHRASE = "PHRASE"
SYNONYM = "SYNONYM"

DEFAULT_KEYWORD_WEIGHT = 1.0
DEFAULT_PHRASE_WEIGHT = 2.0
DEFAULT_SYNONYM_WEIGHT = 0.75
SUBJECT_MULTIPLIER = 1.5
DEFAULT_CONFIDENCE_THRESHOLD = 0.40
DEFAULT_AMBIGUITY_MARGIN = 0.15

_MASK_CHAR = "#"


# --------------------------------------------------------------------------- #
# Text helpers
# --------------------------------------------------------------------------- #
def normalize_text(text: Optional[str]) -> str:
    """Lower-case, strip punctuation, collapse whitespace.

    ``401(k)`` and ``401k`` both become ``401k``. Underscores are treated as
    separators. The function is idempotent.
    """
    if not text:
        return ""
    value = unicodedata.normalize("NFKC", text).lower()
    value = re.sub(r"(\d)\s*\(\s*k\s*\)", r"\1k", value)
    value = re.sub(r"[^\w\s]|_", " ", value)
    return re.sub(r"\s+", " ", value).strip()


@lru_cache(maxsize=2048)
def term_pattern(term: str) -> "re.Pattern[str]":
    """Whole-word / whole-phrase regex for an already-normalised term.

    A single trailing ``s`` or ``es`` is tolerated so ``benefits`` matches the
    keyword ``benefit``. ``tax`` never matches ``syntax``.
    """
    body = r"\s+".join(re.escape(word) for word in term.split())
    return re.compile(r"(?<!\w)" + body + r"(?:s|es)?(?!\w)")


def contains_term(normalized_text: str, term: str) -> bool:
    """True when ``term`` occurs as a whole word / phrase in ``normalized_text``."""
    return term_pattern(normalize_text(term)).search(normalized_text) is not None


def _mask(pattern: "re.Pattern[str]", text: str) -> str:
    return pattern.sub(lambda m: _MASK_CHAR * len(m.group(0)), text)


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CategoryRule:
    """Configurable rule set for one category."""

    category: str
    keywords: Tuple[str, ...] = ()
    phrases: Tuple[str, ...] = ()
    synonyms: Tuple[str, ...] = ()
    keyword_weight: float = DEFAULT_KEYWORD_WEIGHT
    phrase_weight: float = DEFAULT_PHRASE_WEIGHT
    synonym_weight: float = DEFAULT_SYNONYM_WEIGHT

    def iter_terms(self) -> List[Tuple[str, str, float]]:
        """Return ``(normalised_term, rule_type, weight)`` de-duplicated and ordered.

        Longer phrases come first so they can consume their component words.
        Multi-word keywords are scored with the phrase weight. When a term is
        listed more than once the highest weight wins.
        """
        best: Dict[str, Tuple[str, float]] = {}

        def offer(raw: str, rule_type: str, weight: float) -> None:
            term = normalize_text(raw)
            if not term:
                return
            current = best.get(term)
            if current is None or weight > current[1]:
                best[term] = (rule_type, weight)

        for kw in self.keywords:
            multi = len(normalize_text(kw).split()) > 1
            offer(kw, PHRASE if multi else KEYWORD, self.phrase_weight if multi else self.keyword_weight)
        for ph in self.phrases:
            offer(ph, PHRASE, self.phrase_weight)
        for sy in self.synonyms:
            offer(sy, SYNONYM, self.synonym_weight)

        return sorted(
            ((t, rt, w) for t, (rt, w) in best.items()),
            key=lambda item: (-len(item[0].split()), -len(item[0]), item[0]),
        )


@dataclass(frozen=True)
class MatchedRule:
    category: str
    term: str
    rule_type: str
    weight: float
    location: str  # "subject" | "description"
    score: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "category": self.category,
            "term": self.term,
            "rule_type": self.rule_type,
            "weight": self.weight,
            "location": self.location,
            "score": self.score,
        }


@dataclass(frozen=True)
class AlternativeCategory:
    category: str
    score: float

    def to_dict(self) -> Dict[str, object]:
        return {"category": self.category, "score": self.score}


@dataclass
class ClassificationResult:
    category: str
    confidence: float
    matched_rules: List[MatchedRule] = field(default_factory=list)
    alternative_categories: List[AlternativeCategory] = field(default_factory=list)
    decision_explanation: str = ""
    is_ambiguous: bool = False
    top_score: float = 0.0
    scores: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "category": self.category,
            "confidence": self.confidence,
            "matched_rules": [m.to_dict() for m in self.matched_rules],
            "alternative_categories": [a.to_dict() for a in self.alternative_categories],
            "decision_explanation": self.decision_explanation,
            "is_ambiguous": self.is_ambiguous,
            "top_score": self.top_score,
            "scores": dict(self.scores),
        }


# --------------------------------------------------------------------------- #
# Default (hard-coded, configurable) rule sets
# --------------------------------------------------------------------------- #
PAYROLL_RULE = CategoryRule(
    category="PAYROLL",
    keywords=(
        "salary", "payslip", "deduction", "tax", "payment", "pay slip", "salary credit",
        "paycheck", "wage", "compensation", "bonus", "increment", "reimbursement",
    ),
    phrases=(
        "salary not credited", "salary not received", "salary slip", "payment not received",
        "wrong deduction", "incorrect deduction", "tax deduction", "tax form", "pay period",
        "overtime pay", "expense reimbursement", "direct deposit", "salary revision",
    ),
    synonyms=(
        "pay stub", "paystub", "remuneration", "payroll", "net pay", "gross pay", "ctc",
        "form 16", "w2", "overtime", "arrears",
    ),
)

LEAVE_RULE = CategoryRule(
    category="LEAVE",
    keywords=(
        "leave", "vacation", "annual leave", "sick leave", "pto", "time off", "holiday",
        "absence", "maternity", "paternity", "bereavement", "sabbatical",
    ),
    phrases=(
        "unpaid leave", "leave balance", "leave request", "leave application", "medical leave",
        "parental leave", "casual leave", "compensatory off", "leave encashment", "leave policy",
        "paid time off", "leave of absence", "carry forward leave",
    ),
    synonyms=(
        "days off", "day off", "comp off", "out of office", "absent", "off work", "vacation days",
    ),
)

BENEFITS_RULE = CategoryRule(
    category="BENEFITS",
    keywords=(
        "insurance", "health", "dental", "vision", "benefit", "coverage", "enrollment",
        "dependent", "medical", "wellness", "401k", "retirement", "fsa", "hsa",
    ),
    phrases=(
        "health insurance", "dental plan", "vision plan", "open enrollment", "life insurance",
        "medical insurance", "insurance claim", "insurance card", "retirement plan",
        "401k match", "add dependent", "wellness program", "health savings account",
        "flexible spending account", "benefits enrollment",
    ),
    synonyms=(
        "medical cover", "mediclaim", "pension", "provident fund", "health plan", "eap",
    ),
)

ONBOARDING_RULE = CategoryRule(
    category="ONBOARDING",
    keywords=(
        "joining", "onboard", "start date", "offer letter", "background check", "orientation",
        "induction", "new hire", "probation", "contract", "employment letter",
    ),
    phrases=(
        "first day of work", "first day", "joining date", "joining formalities",
        "background verification", "welcome kit", "probation period", "employment contract",
        "orientation session", "induction program", "new joiner",
    ),
    synonyms=(
        "joiner", "bgv", "day one", "preboarding", "pre boarding", "onboarding",
    ),
)

DEFAULT_RULES: Tuple[CategoryRule, ...] = (
    PAYROLL_RULE,
    LEAVE_RULE,
    BENEFITS_RULE,
    ONBOARDING_RULE,
)


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def calculate_match_score(
    subject: Optional[str],
    description: Optional[str],
    rule: CategoryRule,
    subject_multiplier: float = SUBJECT_MULTIPLIER,
) -> Tuple[float, List[MatchedRule]]:
    """Score one ticket against one category's rule set.

    * Each distinct term counts once, however often it appears.
    * A term found in the subject scores ``weight * subject_multiplier``;
      otherwise a description match scores ``weight``.
    * Longer terms are evaluated first and mask the words they cover, so
      "annual leave" does not additionally score the keyword "leave".
    """
    subject_text = normalize_text(subject)
    description_text = normalize_text(description)
    matches: List[MatchedRule] = []
    total = 0.0

    for term, rule_type, weight in rule.iter_terms():
        pattern = term_pattern(term)
        if pattern.search(subject_text):
            score = round(weight * subject_multiplier, 4)
            location = "subject"
        elif pattern.search(description_text):
            score = round(weight, 4)
            location = "description"
        else:
            continue
        subject_text = _mask(pattern, subject_text)
        description_text = _mask(pattern, description_text)
        total += score
        matches.append(MatchedRule(rule.category, term, rule_type, weight, location, score))

    return round(total, 4), matches


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class ClassificationEngine:
    """Classify a ticket into PAYROLL / LEAVE / BENEFITS / ONBOARDING / GENERAL."""

    def __init__(
        self,
        rules: Optional[Iterable[CategoryRule]] = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        ambiguity_margin: float = DEFAULT_AMBIGUITY_MARGIN,
        subject_multiplier: float = SUBJECT_MULTIPLIER,
    ) -> None:
        self.rules: Tuple[CategoryRule, ...] = tuple(rules) if rules is not None else DEFAULT_RULES
        self.confidence_threshold = confidence_threshold
        self.ambiguity_margin = ambiguity_margin
        self.subject_multiplier = subject_multiplier
        self._order: Dict[str, int] = {}
        for index, rule in enumerate(self.rules):
            self._order.setdefault(rule.category, index)

    # ------------------------------------------------------------------ #
    def classify(self, ticket_subject: Optional[str], ticket_description: Optional[str]) -> ClassificationResult:
        scores: Dict[str, float] = {}
        matches_by_category: Dict[str, List[MatchedRule]] = {}
        for rule in self.rules:
            score, matches = calculate_match_score(
                ticket_subject, ticket_description, rule, self.subject_multiplier
            )
            scores[rule.category] = score
            matches_by_category[rule.category] = matches

        ranked: List[Tuple[str, float]] = sorted(
            scores.items(), key=lambda item: (-item[1], self._order[item[0]])
        )
        top_category, top_score = ranked[0] if ranked else (GENERAL, 0.0)

        if top_score <= 0:
            return ClassificationResult(
                category=GENERAL,
                confidence=0.0,
                matched_rules=[],
                alternative_categories=[],
                decision_explanation="No classification rule matched the subject or description.",
                is_ambiguous=False,
                top_score=0.0,
                scores=scores,
            )

        total = sum(scores.values())
        share = top_score / total if total else 0.0
        strength = min(1.0, top_score / 2.0)
        confidence = round(share * strength, 2)
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        is_ambiguous = second_score > 0 and (top_score - second_score) / top_score <= self.ambiguity_margin

        matched = matches_by_category[top_category]
        alternatives = [AlternativeCategory(c, s) for c, s in ranked if s > 0 and c != top_category]

        if confidence < self.confidence_threshold:
            # Not confident enough to commit: report GENERAL, keep the candidate visible.
            candidate = AlternativeCategory(top_category, top_score)
            return ClassificationResult(
                category=GENERAL,
                confidence=confidence,
                matched_rules=matched,
                alternative_categories=[candidate] + alternatives,
                decision_explanation=(
                    "Best candidate %s scored %.2f with confidence %.2f, below the %.2f threshold; "
                    "classified as GENERAL pending clarification."
                    % (top_category, top_score, confidence, self.confidence_threshold)
                ),
                is_ambiguous=False,
                top_score=top_score,
                scores=scores,
            )

        return ClassificationResult(
            category=top_category,
            confidence=confidence,
            matched_rules=matched,
            alternative_categories=alternatives,
            decision_explanation=self._explain(top_category, confidence, matched, alternatives, is_ambiguous),
            is_ambiguous=is_ambiguous,
            top_score=top_score,
            scores=scores,
        )

    # ------------------------------------------------------------------ #
    @staticmethod
    def _explain(
        category: str,
        confidence: float,
        matched: Sequence[MatchedRule],
        alternatives: Sequence[AlternativeCategory],
        is_ambiguous: bool,
    ) -> str:
        terms = ", ".join("'%s' (%s, %s)" % (m.term, m.rule_type.lower(), m.location) for m in matched)
        text = "Classified as %s with confidence %.2f from matches: %s." % (category, confidence, terms)
        if alternatives:
            runner = alternatives[0]
            text += " Runner-up %s scored %.2f." % (runner.category, runner.score)
        if is_ambiguous:
            text += " Scores are close, so the category should be confirmed with the employee."
        return text


# --------------------------------------------------------------------------- #
# Convenience
# --------------------------------------------------------------------------- #
def build_rules_from_entries(entries: Iterable[Tuple[str, str, str, float]]) -> List[CategoryRule]:
    """Build :class:`CategoryRule` objects from ``(category, rule_type, term, weight)`` rows.

    Used to load the editable ``category_rules`` table. Rows keep their own
    weight; term lists are grouped per category in first-seen order.
    """
    grouped: Dict[str, Dict[str, List[Tuple[str, float]]]] = {}
    order: List[str] = []
    for category, rule_type, term, weight in entries:
        if category not in grouped:
            grouped[category] = {KEYWORD: [], PHRASE: [], SYNONYM: []}
            order.append(category)
        grouped[category][rule_type].append((term, weight))

    rules: List[CategoryRule] = []
    for category in order:
        bucket = grouped[category]

        def avg(items: List[Tuple[str, float]], default: float) -> float:
            return items[0][1] if items else default

        rules.append(
            CategoryRule(
                category=category,
                keywords=tuple(t for t, _ in bucket[KEYWORD]),
                phrases=tuple(t for t, _ in bucket[PHRASE]),
                synonyms=tuple(t for t, _ in bucket[SYNONYM]),
                keyword_weight=avg(bucket[KEYWORD], DEFAULT_KEYWORD_WEIGHT),
                phrase_weight=avg(bucket[PHRASE], DEFAULT_PHRASE_WEIGHT),
                synonym_weight=avg(bucket[SYNONYM], DEFAULT_SYNONYM_WEIGHT),
            )
        )
    return rules


def default_engine() -> ClassificationEngine:
    return ClassificationEngine()
