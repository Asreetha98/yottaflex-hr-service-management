from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.policy import PolicyCitation, PolicyDocument, PolicyVersion
from app.repositories.base_repository import BaseRepository


class PolicyRepository(BaseRepository[PolicyDocument]):
    def __init__(self, db: Session) -> None:
        super().__init__(PolicyDocument, db)

    def versions(self, policy_id: str) -> List[PolicyVersion]:
        return (
            self.db.query(PolicyVersion)
            .filter(PolicyVersion.policy_id == policy_id, PolicyVersion.is_deleted.is_(False))
            .order_by(PolicyVersion.version_number)
            .all()
        )

    def get_version(self, version_id: str) -> Optional[PolicyVersion]:
        return (
            self.db.query(PolicyVersion)
            .filter(PolicyVersion.version_id == version_id, PolicyVersion.is_deleted.is_(False))
            .first()
        )

    def citations(self, version_id: str) -> List[PolicyCitation]:
        return (
            self.db.query(PolicyCitation)
            .filter(PolicyCitation.version_id == version_id)
            .order_by(PolicyCitation.citation_id)
            .all()
        )
