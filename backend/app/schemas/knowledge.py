from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas import ORMModel


class KnowledgeArticleOut(ORMModel):
    article_id: str
    title: str
    summary: Optional[str] = None
    content: str
    category_code: Optional[str] = None
    policy_version_id: Optional[str] = None
    keywords: List[str] = []
    audience: List[str] = []
    status: str
    view_count: int = 0
    published_at: Optional[datetime] = None
    last_reviewed_at: Optional[date] = None


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    category: Optional[str] = None
    reference_date: Optional[date] = None
    limit: int = Field(default=5, ge=1, le=20)


class CitationOut(BaseModel):
    policy_id: str
    policy_title: str
    version_id: str
    version_number: int
    section_reference: Optional[str] = None
    excerpt: Optional[str] = None


class KnowledgeSearchHit(BaseModel):
    article_id: str
    title: str
    answer_snippet: str
    confidence: float
    policy_version_id: Optional[str] = None
    policy_backed: bool = False
    citation: Optional[CitationOut] = None
    matched_terms: List[str] = []


class KnowledgeArticleCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    summary: Optional[str] = None
    content: str = Field(min_length=1)
    category_code: str
    keywords: List[str] = []
    audience: List[str] = Field(default_factory=lambda: ["ALL"])
    policy_version_id: Optional[str] = None
