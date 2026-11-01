"""Knowledge-base search and article management on top of the retrieval engine."""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models.employee import Employee
from app.models.knowledge import Category, KnowledgeArticle
from app.models.policy import PolicyCitation, PolicyDocument, PolicyVersion
from app.rules.knowledge_retrieval_engine import (
    ArticleData,
    CitationData,
    KnowledgeRetrievalEngine,
    RetrievalResult,
)
from app.rules.policy_validity_engine import PolicyVersionData
from app.services.ids import next_id
from app.services.policy_service import employee_context, policy_service, to_version_data


def to_article_data(article: KnowledgeArticle, category_codes: Dict[str, str]) -> ArticleData:
    return ArticleData(
        article_id=article.article_id,
        title=article.title,
        content=article.content,
        summary=article.summary,
        primary_category=category_codes.get(article.primary_category_id, "GENERAL"),
        categories=tuple(category_codes.get(c.category_id, "GENERAL") for c in article.categories),
        keywords=tuple(article.keywords or ()),
        audience=tuple(article.audience or ("ALL",)),
        status=article.status,
        policy_version_id=article.policy_version_id,
        is_deleted=article.is_deleted,
    )


class KnowledgeService:
    def category_codes(self, db: Session) -> Dict[str, str]:
        return {c.category_id: c.code for c in db.query(Category).all()}

    def build_engine(self, db: Session, today: Optional[date] = None) -> KnowledgeRetrievalEngine:
        codes = self.category_codes(db)
        articles = (
            db.query(KnowledgeArticle)
            .filter(KnowledgeArticle.is_deleted.is_(False), KnowledgeArticle.status == "PUBLISHED")
            .all()
        )
        policy_engine = policy_service.build_engine(db, today)
        versions: Dict[str, PolicyVersionData] = {
            v.version_id: to_version_data(v)
            for v in db.query(PolicyVersion).filter(PolicyVersion.is_deleted.is_(False)).all()
        }
        titles = {p.policy_id: p.title for p in db.query(PolicyDocument).all()}
        citations = [
            CitationData(c.version_id, c.section_reference, c.excerpt, c.article_id, c.citation_id)
            for c in db.query(PolicyCitation).all()
        ]
        return KnowledgeRetrievalEngine(
            [to_article_data(a, codes) for a in articles], policy_engine, versions, titles, citations
        )

    def search(
        self, db: Session, query: str, category: Optional[str] = None,
        employee: Optional[Employee] = None, reference_date: Optional[date] = None,
        is_sensitive: bool = False, limit: int = 5, today: Optional[date] = None,
    ) -> List[RetrievalResult]:
        engine = self.build_engine(db, today)
        return engine.search(
            query, category, employee_context(employee) if employee else None,
            reference_date, is_sensitive, limit,
        )

    def get_article(self, db: Session, article_id: str, count_view: bool = False) -> KnowledgeArticle:
        article = (
            db.query(KnowledgeArticle)
            .filter(KnowledgeArticle.article_id == article_id, KnowledgeArticle.is_deleted.is_(False))
            .first()
        )
        if article is None:
            raise NotFoundError("Article %s not found" % article_id)
        if count_view:
            article.view_count += 1
            db.flush()
        return article

    def list_articles(
        self, db: Session, category_code: Optional[str] = None, status: Optional[str] = "PUBLISHED",
        skip: int = 0, limit: int = 50,
    ) -> Tuple[List[KnowledgeArticle], int]:
        query = db.query(KnowledgeArticle).filter(KnowledgeArticle.is_deleted.is_(False))
        if status:
            query = query.filter(KnowledgeArticle.status == status)
        if category_code:
            query = query.join(Category, Category.category_id == KnowledgeArticle.primary_category_id).filter(
                Category.code == category_code
            )
        total = query.count()
        items = query.order_by(KnowledgeArticle.article_id).offset(skip).limit(limit).all()
        return items, total

    def create_article(
        self, db: Session, title: str, content: str, category_code: str, actor_user_id: Optional[str],
        summary: Optional[str] = None, keywords: Optional[List[str]] = None,
        audience: Optional[List[str]] = None, policy_version_id: Optional[str] = None,
    ) -> KnowledgeArticle:
        category = db.query(Category).filter(Category.code == category_code).first()
        if category is None:
            raise NotFoundError("Category %s not found" % category_code)
        article = KnowledgeArticle(
            article_id=next_id(db, KnowledgeArticle.article_id, "KB-", 6),
            title=title, content=content, summary=summary,
            primary_category_id=category.category_id,
            policy_version_id=policy_version_id,
            keywords=keywords or [], audience=audience or ["ALL"],
            status="DRAFT", author_id=actor_user_id,
        )
        db.add(article)
        db.flush()
        return article


knowledge_service = KnowledgeService()
