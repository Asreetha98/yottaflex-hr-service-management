"""Policy version validity.

Answers "which version of this policy applied on date D, for this employee?"
without ever falling back to "the newest row".  Four different notions of
"latest" are kept distinct:

* ``latest_created``          highest version number / creation time, even a DRAFT
* ``latest_published``        most recently published, even if not yet effective
* ``currently_effective``     published and effective *today*
* ``historically_effective``  published and effective on a *past* reference date

The engine is pure: callers pass plain :class:`PolicyVersionData` objects.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# Exception codes
POLICY_NOT_FOUND = "POLICY_NOT_FOUND"
POLICY_RETIRED = "POLICY_RETIRED"
NO_VERSIONS = "NO_VERSIONS"
NO_PUBLISHED_VERSION = "NO_PUBLISHED_VERSION"
NOT_YET_EFFECTIVE = "NOT_YET_EFFECTIVE"
EXPIRED = "EXPIRED"
NO_EFFECTIVE_VERSION = "NO_EFFECTIVE_VERSION"
AUDIENCE_MISMATCH = "AUDIENCE_MISMATCH"

DRAFT = "DRAFT"
PUBLISHED = "PUBLISHED"
ARCHIVED = "ARCHIVED"

AUDIENCE_ALL = "ALL"
AUDIENCE_DEPARTMENT = "DEPARTMENT"
AUDIENCE_EMPLOYMENT_TYPE = "EMPLOYMENT_TYPE"
AUDIENCE_LOCATION = "LOCATION"

_EPOCH = datetime(1970, 1, 1)


@dataclass(frozen=True)
class PolicyVersionData:
    version_id: str
    policy_id: str
    version_number: int
    status: str
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    audiences: Tuple[Tuple[str, Optional[str]], ...] = ()  # (audience_type, audience_value)
    title: str = ""

    @property
    def published_date(self) -> Optional[date]:
        return self.published_at.date() if self.published_at else None


@dataclass
class PolicyException:
    code: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass
class PolicyValidityResult:
    policy_id: str
    reference_date: date
    version: Optional[PolicyVersionData] = None
    exception: Optional[PolicyException] = None
    latest_created: Optional[PolicyVersionData] = None
    latest_published: Optional[PolicyVersionData] = None
    currently_effective: Optional[PolicyVersionData] = None
    historically_effective: Optional[PolicyVersionData] = None
    overlap_detected: bool = False
    explanation: str = ""

    @property
    def is_valid(self) -> bool:
        return self.version is not None and self.exception is None

    def to_dict(self) -> Dict[str, object]:
        def vid(v: Optional[PolicyVersionData]) -> Optional[str]:
            return v.version_id if v else None

        return {
            "policy_id": self.policy_id,
            "reference_date": self.reference_date.isoformat(),
            "version_id": vid(self.version),
            "exception": self.exception.to_dict() if self.exception else None,
            "latest_created": vid(self.latest_created),
            "latest_published": vid(self.latest_published),
            "currently_effective": vid(self.currently_effective),
            "historically_effective": vid(self.historically_effective),
            "overlap_detected": self.overlap_detected,
            "explanation": self.explanation,
        }


# --------------------------------------------------------------------------- #
# Audience matching
# --------------------------------------------------------------------------- #
def build_employee_context(
    department_id: Optional[str] = None,
    employment_type: Optional[str] = None,
    location: Optional[str] = None,
) -> Dict[str, str]:
    ctx: Dict[str, str] = {}
    if department_id:
        ctx[AUDIENCE_DEPARTMENT] = department_id
    if employment_type:
        ctx[AUDIENCE_EMPLOYMENT_TYPE] = employment_type
    if location:
        ctx[AUDIENCE_LOCATION] = location
    return ctx


def parse_audience_tokens(tokens: Iterable[str]) -> Tuple[Tuple[str, Optional[str]], ...]:
    """Convert ``["ALL"]`` / ``["DEPARTMENT:DEPT-03", "LOCATION:US"]`` to audience tuples."""
    parsed: List[Tuple[str, Optional[str]]] = []
    for token in tokens:
        if ":" in token:
            kind, value = token.split(":", 1)
            parsed.append((kind.strip().upper(), value.strip()))
        else:
            parsed.append((token.strip().upper(), None))
    return tuple(parsed)


def audience_matches(
    audiences: Sequence[Tuple[str, Optional[str]]], employee: Mapping[str, str]
) -> bool:
    """Same-type rows are OR-ed, different types AND-ed; ``ALL`` / no rows match anyone.

    An employee attribute that is missing for a restricted type cannot be verified
    and therefore does not match.
    """
    if not audiences or any(kind == AUDIENCE_ALL for kind, _ in audiences):
        return True
    by_type: Dict[str, List[Optional[str]]] = {}
    for kind, value in audiences:
        by_type.setdefault(kind, []).append(value)
    for kind, values in by_type.items():
        actual = employee.get(kind)
        if actual is None or actual not in values:
            return False
    return True


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class PolicyValidityEngine:
    """Find the version of a policy that is valid for a date and an employee.

    ``policies`` optionally maps ``policy_id -> status`` (``ACTIVE`` / ``RETIRED``)
    so retired and unknown policies are reported distinctly.
    ``today`` is injectable so results are reproducible.
    """

    def __init__(
        self,
        versions: Iterable[PolicyVersionData],
        policies: Optional[Mapping[str, str]] = None,
        today: Optional[date] = None,
    ) -> None:
        self._by_policy: Dict[str, List[PolicyVersionData]] = {}
        for version in versions:
            self._by_policy.setdefault(version.policy_id, []).append(version)
        for items in self._by_policy.values():
            items.sort(key=lambda v: v.version_number)
        self._policies: Dict[str, str] = dict(policies) if policies is not None else {}
        self.today: date = today or date.today()

    # ------------------------------------------------------------------ #
    def is_effective(self, version: PolicyVersionData, on_date: date) -> bool:
        """The effective test from BUSINESS_RULES section 4.2."""
        if version.status == DRAFT:
            return False
        if version.published_at is None or version.published_date > on_date:  # type: ignore[operator]
            return False
        if version.effective_from is None or version.effective_from > on_date:
            return False
        if version.effective_to is not None and on_date > version.effective_to:
            return False
        if version.status == PUBLISHED:
            return True
        if version.status == ARCHIVED:
            return on_date < self.today  # archived versions only count for history
        return False

    # ------------------------------------------------------------------ #
    @staticmethod
    def _latest_created(versions: Sequence[PolicyVersionData]) -> Optional[PolicyVersionData]:
        if not versions:
            return None
        return max(versions, key=lambda v: (v.created_at or _EPOCH, v.version_number))

    @staticmethod
    def _latest_published(versions: Sequence[PolicyVersionData]) -> Optional[PolicyVersionData]:
        published = [v for v in versions if v.status == PUBLISHED and v.published_at is not None]
        if not published:
            return None
        return max(published, key=lambda v: (v.published_at, v.version_number))  # type: ignore[arg-type,return-value]

    def _effective_candidates(self, versions: Sequence[PolicyVersionData], on_date: date) -> List[PolicyVersionData]:
        found = [v for v in versions if self.is_effective(v, on_date)]
        return sorted(found, key=lambda v: (v.effective_from, v.version_number), reverse=True)  # type: ignore[arg-type,return-value]

    # ------------------------------------------------------------------ #
    def get_effective_version(
        self,
        policy_id: str,
        reference_date: date,
        employee_dept: Optional[str] = None,
        employee_audience: Optional[Mapping[str, str]] = None,
    ) -> PolicyValidityResult:
        """Return the version in force on ``reference_date`` for the employee.

        ``employee_dept`` is a department id; ``employee_audience`` may carry
        ``EMPLOYMENT_TYPE`` and ``LOCATION`` (and ``DEPARTMENT``) values.
        """
        if isinstance(reference_date, datetime):
            reference_date = reference_date.date()
        result = PolicyValidityResult(policy_id=policy_id, reference_date=reference_date)
        versions = self._by_policy.get(policy_id, [])

        known = policy_id in self._policies or bool(versions)
        if not known:
            return self._fail(result, POLICY_NOT_FOUND, "Policy %s does not exist." % policy_id)
        if self._policies.get(policy_id) == "RETIRED":
            return self._fail(result, POLICY_RETIRED, "Policy %s is retired." % policy_id)
        if not versions:
            return self._fail(result, NO_VERSIONS, "Policy %s has no versions." % policy_id)

        result.latest_created = self._latest_created(versions)
        result.latest_published = self._latest_published(versions)
        current = self._effective_candidates(versions, self.today)
        result.currently_effective = current[0] if current else None

        employee: Dict[str, str] = dict(employee_audience or {})
        if employee_dept:
            employee[AUDIENCE_DEPARTMENT] = employee_dept
        check_audience = bool(employee)

        candidates = self._effective_candidates(versions, reference_date)
        if reference_date < self.today and candidates:
            result.historically_effective = candidates[0]

        if not candidates:
            return self._explain_missing(result, versions, reference_date)

        eligible = [v for v in candidates if not check_audience or audience_matches(v.audiences, employee)]
        if not eligible:
            return self._fail(
                result,
                AUDIENCE_MISMATCH,
                "Versions effective on %s exist for %s but none targets this employee."
                % (reference_date, policy_id),
            )

        result.version = eligible[0]
        result.overlap_detected = len(eligible) > 1
        kind = "historically effective" if reference_date < self.today else "currently effective"
        result.explanation = "%s is the %s version of %s on %s" % (
            result.version.version_id, kind, policy_id, reference_date,
        )
        if result.latest_created and result.latest_created.version_id != result.version.version_id:
            result.explanation += " (latest created %s is not in force)" % result.latest_created.version_id
        if result.overlap_detected:
            result.explanation += "; overlapping effective versions detected"
        result.explanation += "."
        return result

    # ------------------------------------------------------------------ #
    @staticmethod
    def _fail(result: PolicyValidityResult, code: str, message: str) -> PolicyValidityResult:
        result.exception = PolicyException(code, message)
        result.explanation = message
        return result

    def _explain_missing(
        self, result: PolicyValidityResult, versions: Sequence[PolicyVersionData], on_date: date
    ) -> PolicyValidityResult:
        released = [v for v in versions if v.status in (PUBLISHED, ARCHIVED) and v.published_at is not None]
        if not released:
            return self._fail(
                result, NO_PUBLISHED_VERSION, "Policy %s has no published version." % result.policy_id
            )
        if all(v.effective_from is None or v.effective_from > on_date for v in released):
            first = min((v.effective_from for v in released if v.effective_from), default=None)
            return self._fail(
                result,
                NOT_YET_EFFECTIVE,
                "No version of %s is effective on %s; the earliest starts %s."
                % (result.policy_id, on_date, first),
            )
        if all(v.effective_to is not None and v.effective_to < on_date for v in released):
            return self._fail(
                result, EXPIRED, "All published versions of %s expired before %s." % (result.policy_id, on_date)
            )
        return self._fail(
            result,
            NO_EFFECTIVE_VERSION,
            "No published version of %s covers %s (gap, late publication or archived)."
            % (result.policy_id, on_date),
        )
