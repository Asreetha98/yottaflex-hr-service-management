"""Deterministic sensitive-case detection (harassment, discrimination, misconduct, ...).

Design bias: favour false positives. Re-routing a harmless ticket is cheap;
exposing a confidential case to the wrong people is not.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from app.rules.classification_engine import contains_term, normalize_text

SENSITIVE_KEYWORDS: Tuple[str, ...] = (
    "harassment", "discrimination", "retaliation", "hostile", "bullying", "grievance",
    "complaint", "disciplinary", "termination", "wrongful", "misconduct", "investigation",
    "confidential", "abuse",
)

# Inflected / related forms that clearly signal the same concern.
KEYWORD_VARIANTS: Dict[str, Tuple[str, ...]] = {
    "harassment": ("harassed", "harass", "harassing", "sexual harassment"),
    "discrimination": ("discriminated", "discriminate", "discriminatory"),
    "retaliation": ("retaliate", "retaliated", "retaliating"),
    "bullying": ("bullied", "bully"),
    "abuse": ("abused", "abusive"),
    "misconduct": (),
    "investigation": ("investigate", "investigating"),
    "disciplinary": ("disciplined",),
}

SENSITIVE_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("being_harassed_or_bullied", r"\bbeing (?:harass\w*|bull\w*|discriminat\w*|threaten\w*|target\w*)\b"),
    ("feeling_unsafe", r"\bfeel(?:ing|s)? (?:unsafe|threatened|intimidated|targeted)\b"),
    ("report_manager_or_colleague", r"\breport(?:ing)? (?:my|a|the) (?:manager|supervisor|boss|colleague|coworker|co worker|lead)\b"),
    ("hostile_environment", r"\bhostile (?:work|working|environment|workplace)\b"),
    ("wrongful_termination", r"\bwrongful(?:ly)? (?:terminat\w*|dismiss\w*|fired)\b"),
    ("legal_action", r"\b(?:legal action|lawsuit|sue|sued|lawyer|attorney)\b"),
    ("whistleblowing", r"\bwhistle ?blow\w*\b"),
    ("unfair_treatment", r"\bunfair(?:ly)? (?:treat\w*|target\w*|dismiss\w*)\b"),
    ("inappropriate_behaviour", r"\binappropriate (?:behavio\w*|comment\w*|touch\w*|conduct)\b"),
    ("raise_formal_complaint", r"\b(?:formal|file|filing|raise|raising|lodge|lodging) (?:a )?(?:formal )?(?:complaint|grievance)\b"),
)

SENSITIVE_QUEUE = "EMPLOYEE_RELATIONS"
ACCESS_RESTRICTED = "RESTRICTED"
ACCESS_STANDARD = "STANDARD"


@dataclass(frozen=True)
class SensitiveMatch:
    kind: str  # "keyword" | "pattern"
    name: str
    matched_text: str

    def to_dict(self) -> Dict[str, str]:
        return {"kind": self.kind, "name": self.name, "matched_text": self.matched_text}


@dataclass
class SensitiveDetectionResult:
    is_sensitive: bool
    matched_patterns: List[str] = field(default_factory=list)
    routing_queue: Optional[str] = None
    access_level: str = ACCESS_STANDARD
    matches: List[SensitiveMatch] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "is_sensitive": self.is_sensitive,
            "matched_patterns": list(self.matched_patterns),
            "routing_queue": self.routing_queue,
            "access_level": self.access_level,
            "matches": [m.to_dict() for m in self.matches],
            "explanation": self.explanation,
        }


class SensitiveRoutingEngine:
    """Detects sensitive HR cases from ticket text."""

    def __init__(
        self,
        keywords: Optional[Iterable[str]] = None,
        patterns: Optional[Iterable[Tuple[str, str]]] = None,
        variants: Optional[Dict[str, Tuple[str, ...]]] = None,
        routing_queue: str = SENSITIVE_QUEUE,
    ) -> None:
        self.keywords: Tuple[str, ...] = tuple(keywords) if keywords is not None else SENSITIVE_KEYWORDS
        self.variants = variants if variants is not None else KEYWORD_VARIANTS
        raw_patterns = tuple(patterns) if patterns is not None else SENSITIVE_PATTERNS
        self._patterns = [(name, re.compile(rx)) for name, rx in raw_patterns]
        self.routing_queue = routing_queue

    def detect(self, subject: Optional[str], description: Optional[str]) -> SensitiveDetectionResult:
        text = normalize_text("%s . %s" % (subject or "", description or ""))
        matches: List[SensitiveMatch] = []
        seen = set()

        for keyword in self.keywords:
            for form in (keyword,) + tuple(self.variants.get(keyword, ())):
                if contains_term(text, form) and keyword not in seen:
                    seen.add(keyword)
                    matches.append(SensitiveMatch("keyword", keyword, form))

        for name, regex in self._patterns:
            found = regex.search(text)
            if found:
                matches.append(SensitiveMatch("pattern", name, found.group(0)))

        if not matches:
            return SensitiveDetectionResult(
                is_sensitive=False,
                explanation="No sensitive keyword or pattern detected.",
            )

        names = [m.name for m in matches]
        return SensitiveDetectionResult(
            is_sensitive=True,
            matched_patterns=names,
            routing_queue=self.routing_queue,
            access_level=ACCESS_RESTRICTED,
            matches=matches,
            explanation=(
                "Sensitive content detected (%s); ticket is RESTRICTED and routed to %s."
                % (", ".join(names), self.routing_queue)
            ),
        )

    @staticmethod
    def can_view(
        ticket_is_sensitive: bool,
        is_requester: bool,
        is_admin: bool,
        has_sensitive_authorization: bool,
    ) -> bool:
        """Visibility rule for RESTRICTED tickets."""
        if not ticket_is_sensitive:
            return True
        return is_requester or is_admin or has_sensitive_authorization
