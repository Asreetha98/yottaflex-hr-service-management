"""Authentication: login, token issue, user lookup."""

from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.exceptions import AuthenticationError
from app.models.base import utcnow
from app.models.user import UserAccount
from app.security.auth import create_access_token
from app.security.password import verify_password
from app.services.audit_service import AuditService

audit = AuditService()


class AuthService:
    def authenticate(self, db: Session, username: str, password: str, ip_address: Optional[str] = None) -> UserAccount:
        user = (
            db.query(UserAccount)
            .filter(UserAccount.username == username, UserAccount.is_deleted.is_(False))
            .first()
        )
        # Same error for unknown user and bad password: no account enumeration.
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            audit.record(
                db, "LOGIN_FAILED", "LOGIN", "user_accounts", user.user_id if user else None,
                actor_user_id=user.user_id if user else None,
                new_values={"username": username}, ip_address=ip_address,
            )
            db.commit()
            raise AuthenticationError("Incorrect username or password")
        user.last_login_at = utcnow()
        audit.record(db, "LOGIN_SUCCESS", "LOGIN", "user_accounts", user.user_id, user, ip_address=ip_address)
        db.commit()
        return user

    def login(self, db: Session, username: str, password: str, ip_address: Optional[str] = None) -> Tuple[str, UserAccount]:
        user = self.authenticate(db, username, password, ip_address)
        return create_access_token(user.user_id, user.role_names), user

    def logout(self, db: Session, user: UserAccount, ip_address: Optional[str] = None) -> None:
        # Tokens are stateless; the client discards the token. The event is audited.
        audit.record(db, "LOGOUT", "LOGOUT", "user_accounts", user.user_id, user, ip_address=ip_address)
        db.commit()


auth_service = AuthService()
