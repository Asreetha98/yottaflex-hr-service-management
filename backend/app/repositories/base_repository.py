"""Generic CRUD base with centralised soft-delete filtering."""

from typing import Any, Generic, List, Optional, Sequence, Tuple, Type, TypeVar

from sqlalchemy.orm import Session

from app.models.base import Base, utcnow

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    def __init__(self, model: Type[ModelT], db: Session) -> None:
        self.model = model
        self.db = db
        mapper = model.__mapper__
        self.pk = mapper.primary_key[0]

    def _query(self, include_deleted: bool = False):
        query = self.db.query(self.model)
        if not include_deleted and hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted.is_(False))  # type: ignore[attr-defined]
        return query

    def get(self, pk: Any, include_deleted: bool = False) -> Optional[ModelT]:
        return self._query(include_deleted).filter(self.pk == pk).first()

    def list(self, skip: int = 0, limit: int = 50, filters: Optional[Sequence[Any]] = None,
             order_by: Optional[Any] = None) -> List[ModelT]:
        query = self._query()
        for condition in filters or ():
            query = query.filter(condition)
        return query.order_by(order_by if order_by is not None else self.pk).offset(skip).limit(limit).all()

    def count(self, filters: Optional[Sequence[Any]] = None) -> int:
        query = self._query()
        for condition in filters or ():
            query = query.filter(condition)
        return query.count()

    def paginate(self, skip: int = 0, limit: int = 50, filters: Optional[Sequence[Any]] = None,
                 order_by: Optional[Any] = None) -> Tuple[List[ModelT], int]:
        return self.list(skip, limit, filters, order_by), self.count(filters)

    def add(self, entity: ModelT) -> ModelT:
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: ModelT, **changes: Any) -> ModelT:
        for key, value in changes.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        if hasattr(entity, "updated_at"):
            entity.updated_at = utcnow()  # type: ignore[attr-defined]
        self.db.flush()
        return entity

    def soft_delete(self, entity: ModelT) -> ModelT:
        if not hasattr(entity, "soft_delete"):
            raise TypeError("%s does not support soft delete" % self.model.__name__)
        entity.soft_delete()  # type: ignore[attr-defined]
        self.db.flush()
        return entity
