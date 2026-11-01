"""JWT creation / validation and the OAuth2 bearer scheme."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Sequence

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import get_settings
from app.exceptions import AuthenticationError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="%s/auth/token" % get_settings().api_v1_prefix)


def create_access_token(
    user_id: str,
    roles: Sequence[str],
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    claims: Dict[str, Any] = {
        "sub": user_id,
        "roles": list(roles),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired token") from exc
