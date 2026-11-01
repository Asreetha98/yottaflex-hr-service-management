"""Load generated CSVs into the application database (run on a fresh/empty database).

    cd backend && python -m generator.load_to_db --input ../generator/output
Uses DATABASE_URL (default SQLite file). Tables are created if missing; reference seeding is NOT run,
because the generated CSVs already contain roles, permissions, rules, calendars and demo users.
"""

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime, time
from typing import Any

import generator  # noqa: F401  (puts backend/ on sys.path)
from generator.utils.dataset import COLUMNS


def convert(column: Any, raw: str) -> Any:
    from sqlalchemy import Boolean, Date, Float, Integer, JSON, Numeric, Time
    from app.models.base import UTCDateTime
    if raw == "":
        return None
    kind = column.type
    if isinstance(kind, Boolean):
        return raw == "true"
    if isinstance(kind, Integer):
        return int(raw)
    if isinstance(kind, (Float, Numeric)):
        return float(raw)
    if isinstance(kind, Time):
        return time.fromisoformat(raw)
    if isinstance(kind, UTCDateTime):
        return datetime.fromisoformat(raw)
    if isinstance(kind, Date):
        return date.fromisoformat(raw)
    if isinstance(kind, JSON):
        return json.loads(raw)
    return raw


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="../generator/output")
    args = parser.parse_args(argv)

    import app.models  # noqa: F401
    from app.database import engine
    from app.models.base import Base

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for table in COLUMNS:
            sa_table = Base.metadata.tables[table]
            path = os.path.join(args.input, "%s.csv" % table)
            with open(path, "r", encoding="utf-8", newline="") as handle:
                rows = [{c: convert(sa_table.c[c], v) for c, v in r.items() if c in sa_table.c}
                        for r in csv.DictReader(handle)]
            if table == "user_accounts":
                # CSVs carry a placeholder so output stays byte-identical; real (salted) hashes are set at load time.
                from app.config import get_settings
                from app.security.password import hash_password
                shared = hash_password(get_settings().demo_user_password)
                for row in rows:
                    row["password_hash"] = shared
            for start in range(0, len(rows), 2000):
                conn.execute(sa_table.insert(), rows[start:start + 2000])
            print("loaded %-26s %6d rows" % (table, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
