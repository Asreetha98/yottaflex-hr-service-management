"""Human-readable deterministic ID allocation.

``SessionLocal`` runs with ``autoflush=False``; callers must ``db.flush()`` after
adding a row so the next allocation sees it.
"""

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session


def next_id(db: Session, column: Any, prefix: str, width: int, start: int = 1) -> str:
    """Return ``prefix`` + zero-padded (max existing suffix + 1).

    Works because suffixes are fixed-width, so the lexical maximum is also the
    numeric maximum.
    """
    top = db.query(func.max(column)).filter(column.like(prefix + "%")).scalar()
    number = start
    if top:
        try:
            number = int(top[len(prefix):]) + 1
        except ValueError:
            number = start
    return "%s%0*d" % (prefix, width, number)
