from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.knowledge import Category, KnowledgeArticle
from app.repositories.base_repository import BaseRepository


class KnowledgeRepository(BaseRepository[KnowledgeArticle]):
    def __init__(self, db: Session) -> None:
        super().__init__(KnowledgeArticle, db)

    def published(self, skip: int = 0, limit: int = 50) -> List[KnowledgeArticle]:
        return self.list(skip, limit, [KnowledgeArticle.status == "PUBLISHED"], KnowledgeArticle.article_id)

    def by_category_code(self, code: str, skip: int = 0, limit: int = 50) -> List[KnowledgeArticle]:
        return (
            self._query()
            .join(Category, Category.category_id == KnowledgeArticle.primary_category_id)
            .filter(Category.code == code, KnowledgeArticle.status == "PUBLISHED")
            .order_by(KnowledgeArticle.article_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def categories(self) -> List[Category]:
        return self.db.query(Category).filter(Category.is_deleted.is_(False)).order_by(Category.category_id).all()

    def get_category_by_code(self, code: str) -> Optional[Category]:
        return self.db.query(Category).filter(Category.code == code).first()
