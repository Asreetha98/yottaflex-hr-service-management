"""Deterministic knowledge-base retrieval.

Pipeline: candidate filter -> category filter -> keyword / phrase / synonym /
title / category scoring -> audience validation -> policy-version validation ->
confidence cut-off -> stable ordering.  No embeddings, no model.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from app.rules.classification_engine import GENERAL, contains_term, normalize_text
from app.rules.policy_validity_engine import (
    PolicyValidityEngine,
    PolicyVersionData,
    audience_matches,
    parse_audience_tokens,
)

EXACT_KEYWORD_SCORE = 3.0
PHRASE_SCORE = 4.0
SYNONYM_SCORE = 1.5
TITLE_WORD_SCORE = 1.0
CATEGORY_SCORE = 2.0
CONFIDENCE_DIVISOR = 10.0
MIN_CONFIDENCE = 0.2
MAX_RESULTS = 5
SNIPPET_LENGTH = 300

STOPWORDS = frozenset(
    "a an and are as at be by for from has have how i in is it my of on or our that the this to was what when "
    "where which who will with can do does please need want would me we you your about".split()
)

DEFAULT_SYNONYMS: Tuple[Tuple[str, ...], ...] = (
    ("salary", "pay", "wage", "paycheck", "remuneration", "compensation"),
    ("payslip", "pay slip", "pay stub", "salary slip"),
    ("leave", "time off", "pto", "vacation", "absence", "days off"),
    ("insurance", "mediclaim", "medical cover", "coverage"),
    ("retirement", "pension", "401k", "provident fund"),
    ("onboarding", "joining", "induction", "orientation", "new hire"),
    ("reimbursement", "expense claim", "refund"),
    ("contract", "employment letter", "offer letter"),
)


@dataclass(frozen=True)
class ArticleData:
    article_id: str
    title: str
    content: str
    primary_category: str
    summary: Optional[str] = None
    categories: Tuple[str, ...] = ()
    keywords: Tuple[str, ...] = ()
    audience: Tuple[str, ...] = ("ALL",)
    status: str = "PUBLISHED"
    policy_version_id: Optional[str] = None
    is_deleted: bool = False


@dataclass(frozen=True)
class CitationData:
    version_id: str
    section_reference: str
    excerpt: str
    article_id: Optional[str] = None
    citation_id: Optional[str] = None


@dataclass
class Citation:
    policy_id: str
    policy_title: str
    version_id: str
    version_number: int
    section_reference: Optional[str] = None
    excerpt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class RetrievalResult:
    article: ArticleData
    policy_version: Optional[PolicyVersionData]
    answer_snippet: str
    citation: Optional[Citation]
    confidence: float
    matched_terms: List[str] = field(default_factory=list)
    score: float = 0.0
    policy_backed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_id": self.article.article_id,
            "title": self.article.title,
            "policy_version_id": self.policy_version.version_id if self.policy_version else None,
            "answer_snippet": self.answer_snippet,
            "citation": self.citation.to_dict() if self.citation else None,
            "confidence": self.confidence,
            "matched_terms": list(self.matched_terms),
            "policy_backed": self.policy_backed,
        }


@dataclass
class RetrievalRejection:
    article_id: str
    reason: str


class KnowledgeRetrievalEngine:
    def __init__(
        self,
        articles: Iterable[ArticleData],
        policy_engine: Optional[PolicyValidityEngine] = None,
        versions: Optional[Mapping[str, PolicyVersionData]] = None,
        policy_titles: Optional[Mapping[str, str]] = None,
        citations: Optional[Iterable[CitationData]] = None,
        synonyms: Optional[Iterable[Sequence[str]]] = None,
    ) -> None:
        self.articles: Tuple[ArticleData, ...] = tuple(articles)
        self.policy_engine = policy_engine
        self.versions: Dict[str, PolicyVersionData] = dict(versions or {})
        self.policy_titles: Dict[str, str] = dict(policy_titles or {})
        self._citations: Dict[str, List[CitationData]] = {}
        for citation in citations or ():
            self._citations.setdefault(citation.version_id, []).append(citation)
        groups = tuple(tuple(normalize_text(t) for t in g) for g in (synonyms or DEFAULT_SYNONYMS))
        self._synonym_index: Dict[str, List[str]] = {}
        for group in groups:
            for term in group:
                others = [t for t in group if t != term]
                self._synonym_index.setdefault(term, []).extend(others)
        self.rejections: List[RetrievalRejection] = []

    # ------------------------------------------------------------------ #
    def search(
        self,
        query: str,
        category: Optional[str] = None,
        employee: Optional[Mapping[str, str]] = None,
        reference_date: Optional[date] = None,
        is_sensitive: bool = False,
        limit: int = MAX_RESULTS,
    ) -> List[RetrievalResult]:
        self.rejections = []
        if is_sensitive:  # rule 1: sensitive tickets never receive articles
            return []
        text = normalize_text(query)
        if not text:
            return []
        ref = reference_date or (self.policy_engine.today if self.policy_engine else date.today())
        query_words = [w for w in text.split() if w not in STOPWORDS]
        expansions = self._expand(text, query_words)

        results: List[RetrievalResult] = []
        for article in self.articles:
            if article.status != "PUBLISHED" or article.is_deleted:
                continue
            if category and category != GENERAL:
                article_cats = {article.primary_category, *article.categories}
                if category not in article_cats:
                    continue

            score, matched = self._score(article, text, query_words, expansions, category)
            if score <= 0:
                continue

            if employee is not None and not audience_matches(parse_audience_tokens(article.audience), employee):
                self.rejections.append(RetrievalRejection(article.article_id, "AUDIENCE_MISMATCH"))
                continue

            version, reason = self._validate_policy(article, ref, employee)
            if reason:
                self.rejections.append(RetrievalRejection(article.article_id, reason))
                continue

            confidence = round(min(1.0, score / CONFIDENCE_DIVISOR), 2)
            if confidence < MIN_CONFIDENCE:
                continue

            results.append(
                RetrievalResult(
                    article=article,
                    policy_version=version,
                    answer_snippet=self._snippet(article, matched),
                    citation=self._citation(article, version),
                    confidence=confidence,
                    matched_terms=matched,
                    score=score,
                    policy_backed=version is not None,
                )
            )

        results.sort(key=lambda r: (-r.confidence, -r.score, r.article.article_id))
        return results[:limit]

    # ------------------------------------------------------------------ #
    def _expand(self, text: str, query_words: Sequence[str]) -> Dict[str, List[str]]:
        """Map each synonym found in the query to the other members of its group."""
        found: Dict[str, List[str]] = {}
        for term, others in self._synonym_index.items():
            if contains_term(text, term):
                found[term] = [o for o in others if not contains_term(text, o)]
        return found

    def _score(
        self,
        article: ArticleData,
        text: str,
        query_words: Sequence[str],
        expansions: Mapping[str, Sequence[str]],
        category: Optional[str],
    ) -> Tuple[float, List[str]]:
        score = 0.0
        matched: List[str] = []
        keywords = sorted({normalize_text(k) for k in article.keywords if normalize_text(k)})

        for kw in keywords:
            if contains_term(text, kw):
                multi = len(kw.split()) > 1
                score += PHRASE_SCORE if multi else EXACT_KEYWORD_SCORE
                matched.append(kw)

        searchable = " ".join([normalize_text(article.title)] + keywords)
        synonym_hit = set()
        for term, others in expansions.items():
            for other in others:
                if other not in synonym_hit and contains_term(searchable, other):
                    synonym_hit.add(other)
                    score += SYNONYM_SCORE
                    matched.append("%s~%s" % (term, other))

        title = normalize_text(article.title)
        for word in sorted(set(query_words)):
            if contains_term(title, word):
                score += TITLE_WORD_SCORE
                matched.append("title:%s" % word)

        if category and category != GENERAL and score > 0:
            if category in {article.primary_category, *article.categories}:
                score += CATEGORY_SCORE
                matched.append("category:%s" % category)
        return round(score, 4), matched

    def _validate_policy(
        self, article: ArticleData, ref: date, employee: Optional[Mapping[str, str]]
    ) -> Tuple[Optional[PolicyVersionData], Optional[str]]:
        if not article.policy_version_id:
            return None, None  # allowed, but not policy backed
        version = self.versions.get(article.policy_version_id)
        if version is None or self.policy_engine is None:
            return None, "POLICY_VERSION_UNKNOWN"
        verdict = self.policy_engine.get_effective_version(
            version.policy_id, ref, employee_audience=employee
        )
        if verdict.version is None:
            return None, "POLICY_%s" % (verdict.exception.code if verdict.exception else "INVALID")
        if verdict.version.version_id != version.version_id:
            return None, "POLICY_VERSION_NOT_IN_FORCE"
        return version, None

    @staticmethod
    def _snippet(article: ArticleData, matched: Sequence[str]) -> str:
        body = (article.summary or "").strip() or article.content.strip()
        body = " ".join(body.split())
        if len(body) <= SNIPPET_LENGTH:
            return body
        lowered = body.lower()
        anchor = -1
        for term in matched:
            plain = term.split(":", 1)[-1].split("~")[-1]
            anchor = lowered.find(plain)
            if anchor >= 0:
                break
        start = max(0, anchor - SNIPPET_LENGTH // 3) if anchor > 0 else 0
        return body[start:start + SNIPPET_LENGTH].strip()

    def _citation(self, article: ArticleData, version: Optional[PolicyVersionData]) -> Optional[Citation]:
        if version is None:
            return None
        options = self._citations.get(version.version_id, [])
        chosen = next((c for c in options if c.article_id == article.article_id), None) or (
            options[0] if options else None
        )
        return Citation(
            policy_id=version.policy_id,
            policy_title=self.policy_titles.get(version.policy_id, version.title),
            version_id=version.version_id,
            version_number=version.version_number,
            section_reference=chosen.section_reference if chosen else None,
            excerpt=chosen.excerpt if chosen else None,
        )
