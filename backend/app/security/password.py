"""bcrypt password hashing (direct ``bcrypt`` library, no passlib)."""

import bcrypt

# bcrypt only uses the first 72 bytes; truncate explicitly so behaviour is the same
# across bcrypt versions (newer releases raise instead of truncating).
_MAX_BYTES = 72


def _prepare(plain: str) -> bytes:
    return plain.encode("utf-8")[:_MAX_BYTES]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_prepare(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False
