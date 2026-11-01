"""Shared fixtures: an isolated in-memory SQLite DB with reference data and demo users."""

import os
import sys

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["APP_ENV"] = "test"

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(ROOT, "backend")
for path in (BACKEND, ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401
from app.database import SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.seed import seed_all  # noqa: E402

PASSWORD = "ChangeMe123!"


@pytest.fixture(scope="session")
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_all(db, include_demo_users=True)
    finally:
        db.close()
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def login(client, username):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="session")
def tokens(client):
    return {u: login(client, u) for u in ("admin", "hr_partner", "hr_sensitive", "it_ops", "manager", "employee",
                                           "employee2")}
