"""Exactly ``size.articles`` knowledge articles (150 by default) tied to policy versions."""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from generator.config import REFERENCE_DATE, stage_rng
from generator.master_data.departments import sd
from generator.utils.dataset import Dataset
from generator.utils.id_generator import kb_id

GENERIC_TOPICS = {
    "PAYROLL": ("How to read your payslip", "Reporting a missing salary credit", "Updating bank account details",
                "Understanding tax deductions on payslips", "Submitting an expense reimbursement claim",
                "Direct deposit setup guide"),
    "LEAVE": ("How to apply for leave in the portal", "Checking your leave balance", "Cancelling an approved leave request",
              "Public holidays calendar", "Medical leave documentation checklist", "Compensatory off requests"),
    "BENEFITS": ("Enrolling dependents in health insurance", "Filing an insurance claim", "Replacing a lost insurance card",
                 "Open enrollment checklist", "Using the wellness program", "Retirement plan contribution changes"),
    "ONBOARDING": ("Your first day checklist", "Preparing for background verification", "Where to find your offer letter",
                   "Requesting an employment letter", "Orientation session schedule", "Probation review process"),
}
CATEGORY_KEYWORDS = {
    "PAYROLL": ("salary", "payslip", "payroll", "payment"),
    "LEAVE": ("leave", "time off", "vacation", "absence"),
    "BENEFITS": ("benefit", "insurance", "coverage", "enrollment"),
    "ONBOARDING": ("onboarding", "joining", "new hire", "orientation"),
}
CATEGORY_ORDER = ("PAYROLL", "LEAVE", "BENEFITS", "ONBOARDING")


def _audience_tokens(version: Dict[str, Any]) -> List[str]:
    tokens = []
    for kind, value in version["audiences"]:
        tokens.append("ALL" if kind == "ALL" else "%s:%s" % (kind, value))
    return tokens or ["ALL"]


def _in_force(version: Dict[str, Any], today: date) -> bool:
    return (version["status"] == "PUBLISHED" and version["published_at"] is not None
            and version["effective_from"] is not None and version["effective_from"] <= today
            and (version["effective_to"] is None or version["effective_to"] >= today))


def generate_knowledge(ds: Dataset) -> None:
    rng = stage_rng("knowledge")
    categories = ds.extra["category_ids"]
    versions: List[Dict[str, Any]] = ds.extra["version_meta"]
    by_policy: Dict[str, List[Dict[str, Any]]] = {}
    for v in versions:
        by_policy.setdefault(v["policy_id"], []).append(v)
    target = ds.size.articles
    drafts: List[Dict[str, Any]] = []

    def push(**fields: Any) -> None:
        drafts.append(fields)

    # 1) Two policy-backed articles per policy, on the version in force today.
    for pid in sorted(by_policy):
        items = by_policy[pid]
        current = [v for v in items if _in_force(v, REFERENCE_DATE)]
        version = current[-1] if current else items[-1]
        category = version["category"]
        retired = version["retired"]
        status = "ARCHIVED" if retired else "PUBLISHED"
        kws = [version["topic"], version["title"].lower()] + list(CATEGORY_KEYWORDS[category])
        push(title="%s: how it works" % version["title"], summary=version["sentence"],
             content="%s\n\nSource: %s, version %d." % (version["sentence"], version["title"], version["version_number"]),
             category=category, version=version["version_id"], keywords=kws,
             audience=_audience_tokens(version), status=status)
        push(title="Quick answer: %s" % version["topic"], summary=version["sentence"],
             content="Quick answer. %s" % version["sentence"], category=category,
             version=version["version_id"], keywords=kws[:2] + ["faq"],
             audience=_audience_tokens(version), status=status)

    # 2) Historical articles describing superseded versions (kept ARCHIVED).
    for pid in sorted(by_policy):
        items = by_policy[pid]
        for version in items:
            if version["status"] == "ARCHIVED":
                push(title="%s (superseded)" % version["title"], summary=version["sentence"],
                     content="Superseded guidance. %s" % version["sentence"], category=version["category"],
                     version=version["version_id"], keywords=[version["topic"], "previous policy"],
                     audience=_audience_tokens(version), status="ARCHIVED")

    # 3) Generic process articles (no policy dependency); cycle until the target is reached.
    cycle = 0
    while len(drafts) < target:
        category = CATEGORY_ORDER[cycle % 4]
        topics = GENERIC_TOPICS[category]
        index = (cycle // 4) % len(topics)
        title = topics[index]
        round_no = cycle // (4 * len(topics))
        if round_no:
            title = "%s (guide %d)" % (title, round_no + 1)
        audience = ["ALL"]
        if rng.random() < 0.15:
            audience = ["LOCATION:US"]
        push(title=title, summary="Step-by-step guidance: %s." % title.lower(),
             content="%s\n\n1. Sign in to the HR portal.\n2. Open the relevant section.\n3. Follow the on-screen steps "
                     "or raise a ticket if you need help." % title,
             category=category, version=None,
             keywords=[title.lower()] + list(CATEGORY_KEYWORDS[category][:2]),
             audience=audience, status="PUBLISHED")
        cycle += 1
    drafts = drafts[:target]

    citation_by_version = {c["version_id"]: c for c in ds.rows("policy_citations")}
    for number, d in enumerate(drafts, start=1):
        article_id = kb_id(number)
        published = datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc) + timedelta(days=number % 250)
        ds.add("knowledge_articles", article_id=article_id, title=d["title"], summary=d["summary"],
               content=d["content"], primary_category_id=categories[d["category"]],
               policy_version_id=d["version"], keywords=d["keywords"], audience=d["audience"],
               status=d["status"], view_count=rng.randint(0, 900),
               published_at=published if d["status"] != "DRAFT" else None,
               last_reviewed_at=(published + timedelta(days=30)).date(), author_id="USR-000001",
               created_at=published, updated_at=published, **sd())
        if d["version"] and d["version"] in citation_by_version and citation_by_version[d["version"]]["article_id"] is None:
            citation_by_version[d["version"]]["article_id"] = article_id
        if number % 5 == 0:
            secondary = CATEGORY_ORDER[(CATEGORY_ORDER.index(d["category"]) + 1) % 4]
            ds.add("article_categories", article_id=article_id, category_id=categories[secondary])
    ds.extra["article_policy"] = {a["article_id"]: a["policy_version_id"] for a in ds.rows("knowledge_articles")}


def current_version_for(ds: Dataset, policy_id: str, on_date: date) -> Optional[Dict[str, Any]]:
    """Version actually in force for ``policy_id`` on ``on_date`` (ground-truth helper)."""
    candidates = [v for v in ds.extra["version_meta"] if v["policy_id"] == policy_id
                  and v["status"] in ("PUBLISHED", "ARCHIVED") and v["published_at"] is not None
                  and v["published_at"].date() <= on_date and v["effective_from"] is not None
                  and v["effective_from"] <= on_date
                  and (v["effective_to"] is None or v["effective_to"] >= on_date)]
    if not candidates:
        return None
    candidates.sort(key=lambda v: (v["effective_from"], v["version_number"]))
    return candidates[-1]
