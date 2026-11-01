"""Resolution specs (built during ticket simulation) and resolution rows."""

import random
from typing import Any, Dict, List, Optional

from generator.master_data.knowledge import current_version_for
from generator.utils.dataset import Dataset
from app.rules.policy_validity_engine import audience_matches, build_employee_context

RESOLUTION_WEIGHTS = (("POLICY_ANSWER", 40), ("ACTION_COMPLETED", 38), ("REFERRED", 8),
                      ("NO_ACTION_REQUIRED", 9), ("DUPLICATE", 5))
SATISFACTION_WEIGHTS = ((5, 38), (4, 32), (3, 16), (2, 8), (1, 6))
ACTION_TEXT = (
    "The request has been processed and the employee record was updated.",
    "We corrected the issue in the HR system and confirmed the outcome with the employee.",
    "The team completed the requested change; the employee confirmed it looks correct.",
)


def _weighted(rng: random.Random, options: Any) -> Any:
    total = sum(w for _, w in options)
    pick = rng.uniform(0, total)
    running = 0.0
    for value, weight in options:
        running += weight
        if pick <= running:
            return value
    return options[-1][0]


def _lookups(ds: Dataset) -> Dict[str, Any]:
    cache = ds.extra.get("_resolution_lookups")
    if cache is not None:
        return cache
    by_category: Dict[str, List[str]] = {}
    for pid, info in sorted(ds.extra["policy_info"].items()):
        if not info["retired"]:
            by_category.setdefault(info["category"], []).append(pid)
    citations = {c["version_id"]: c["citation_id"] for c in ds.rows("policy_citations")}
    articles: Dict[str, str] = {}
    for art in ds.rows("knowledge_articles"):
        if art["policy_version_id"] and art["status"] == "PUBLISHED":
            articles.setdefault(art["policy_version_id"], art["article_id"])
    cache = {"by_category": by_category, "citations": citations, "articles": articles}
    ds.extra["_resolution_lookups"] = cache
    return cache


def build_spec(rng: random.Random, ds: Dataset, plan: Dict[str, Any], resolver_user: str) -> Dict[str, Any]:
    """Decide how a ticket is resolved. Policy-backed answers cite the version in force on creation."""
    truth = plan["truth"]
    rtype = _weighted(rng, RESOLUTION_WEIGHTS)
    spec: Dict[str, Any] = {
        "resolution_type": rtype, "policy_version_id": None, "citation_id": None, "article_id": None,
        "resolved_by": resolver_user, "was_reopened": False,
        "satisfaction_score": _weighted(rng, SATISFACTION_WEIGHTS) if rng.random() < 0.7 else None,
    }
    if plan["sensitive"]:
        spec["resolution_type"] = "REFERRED"
        spec["summary"] = "Handled by Employee Relations"
        spec["resolution_text"] = ("The case was reviewed by Employee Relations under the confidentiality protocol "
                                   "and the employee has been contacted directly.")
        return spec

    lookups = _lookups(ds)
    category = truth["expected_category"]
    if rtype == "POLICY_ANSWER":
        pids = lookups["by_category"].get(category, [])
        employee = ds.extra["employee_ctx"][plan["requester"]]
        audience = build_employee_context(employee["department_id"], employee["employment_type"], employee["location"])
        chosen: Optional[Dict[str, Any]] = None
        if pids:
            offset = rng.randrange(len(pids))
            for k in range(len(pids)):
                version = current_version_for(ds, pids[(offset + k) % len(pids)], plan["created_at"].date())
                if version and audience_matches(version["audiences"], audience):
                    chosen = version
                    break
        if chosen is None:
            rtype = "ACTION_COMPLETED"
            spec["resolution_type"] = rtype
        else:
            spec["policy_version_id"] = chosen["version_id"]
            spec["citation_id"] = lookups["citations"].get(chosen["version_id"])
            spec["article_id"] = lookups["articles"].get(chosen["version_id"])
            spec["summary"] = "Answered from policy: %s" % chosen["title"]
            spec["resolution_text"] = "As per %s (version %d): %s" % (
                chosen["title"], chosen["version_number"], chosen["sentence"])
            return spec

    if rtype == "ACTION_COMPLETED":
        spec["summary"] = "Action completed"
        spec["resolution_text"] = rng.choice(ACTION_TEXT)
    elif rtype == "REFERRED":
        spec["summary"] = "Referred to the responsible team"
        spec["resolution_text"] = "The request was referred to the specialist team, who completed it."
    elif rtype == "NO_ACTION_REQUIRED":
        spec["summary"] = "No action required"
        spec["resolution_text"] = "No change was needed; the employee was informed of the current position."
    else:
        spec["summary"] = "Duplicate of an existing request"
        spec["resolution_text"] = "This request duplicates an earlier ticket from the same employee."
    return spec


def generate_resolutions(ds: Dataset) -> None:
    for plan in ds.extra["plans"]:
        count = 0
        for step in plan["steps"]:
            if step["kind"] != "resolve":
                continue
            count += 1
            spec = step["details"]["resolution"]
            ds.add("resolutions", resolution_id="RES-%s-%02d" % (plan["ticket_id"], count),
                   ticket_id=plan["ticket_id"], resolution_type=spec["resolution_type"],
                   summary=spec["summary"], resolution_text=spec["resolution_text"],
                   policy_version_id=spec["policy_version_id"], citation_id=spec["citation_id"],
                   article_id=spec["article_id"], resolved_by=spec["resolved_by"], resolved_at=step["ts"],
                   satisfaction_score=spec["satisfaction_score"], was_reopened=spec["was_reopened"],
                   created_at=step["ts"], updated_at=step["ts"], is_deleted=False, deleted_at=None)
