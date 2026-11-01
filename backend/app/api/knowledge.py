from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_permission
from app.models.employee import Employee
from app.models.user import UserAccount
from app.rules.knowledge_retrieval_engine import RetrievalResult
from app.schemas import Page
from app.schemas.knowledge import (
    CitationOut,
    KnowledgeArticleCreate,
    KnowledgeArticleOut,
    KnowledgeSearchHit,
    KnowledgeSearchRequest,
)
from app.services.audit_service import AuditService
from app.services.knowledge_service import knowledge_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
audit = AuditService()


def to_hit(result: RetrievalResult) -> KnowledgeSearchHit:
    return KnowledgeSearchHit(
        article_id=result.article.article_id,
        title=result.article.title,
        answer_snippet=result.answer_snippet,
        confidence=result.confidence,
        policy_version_id=result.policy_version.version_id if result.policy_version else None,
        policy_backed=result.policy_backed,
        citation=CitationOut(**result.citation.to_dict()) if result.citation else None,
        matched_terms=result.matched_terms,
    )


@router.post("/search", response_model=List[KnowledgeSearchHit])
def search(
    body: KnowledgeSearchRequest,
    user: UserAccount = Depends(require_permission("view_knowledge")),
    db: Session = Depends(get_db),
) -> List[KnowledgeSearchHit]:
    employee = (
        db.query(Employee).filter(Employee.employee_id == user.employee_id).first() if user.employee_id else None
    )
    results = knowledge_service.search(
        db, body.query, body.category, employee, body.reference_date, False, body.limit
    )
    return [to_hit(r) for r in results]


@router.get("/articles", response_model=Page[KnowledgeArticleOut])
def list_articles(
    category: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _user: UserAccount = Depends(require_permission("view_knowledge")),
    db: Session = Depends(get_db),
) -> Page[KnowledgeArticleOut]:
    items, total = knowledge_service.list_articles(db, category, "PUBLISHED", skip, limit)
    return Page[KnowledgeArticleOut](items=[KnowledgeArticleOut.model_validate(a) for a in items], total=total, skip=skip, limit=limit)


@router.get("/articles/{article_id}", response_model=KnowledgeArticleOut)
def get_article(article_id: str, _user: UserAccount = Depends(require_permission("view_knowledge")), db: Session = Depends(get_db)) -> KnowledgeArticleOut:
    article = knowledge_service.get_article(db, article_id, count_view=True)
    db.commit()
    return KnowledgeArticleOut.model_validate(article)


@router.post("/articles", response_model=KnowledgeArticleOut, status_code=201)
def create_article(
    body: KnowledgeArticleCreate,
    user: UserAccount = Depends(require_permission("manage_knowledge")),
    db: Session = Depends(get_db),
) -> KnowledgeArticleOut:
    article = knowledge_service.create_article(
        db, body.title, body.content, body.category_code, user.user_id, body.summary,
        body.keywords, body.audience, body.policy_version_id,
    )
    audit.record(db, "ARTICLE_CREATED", "CREATE", "knowledge_articles", article.article_id, user)
    db.commit()
    return KnowledgeArticleOut.model_validate(article)
