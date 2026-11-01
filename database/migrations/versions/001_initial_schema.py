"""initial schema: all 29 tables

Revision ID: 001
Revises:
Create Date: 2026-10-22

Creates every table defined in ``app.models`` (26 entities + 3 bridge tables, see
documentation/DATA_DICTIONARY.md).

IMPLEMENTATION NOTE: this baseline migration builds the schema from the model
metadata (``Base.metadata.create_all``) instead of spelling out 29 ``op.create_table``
calls. It is therefore a snapshot of the models *as of this commit*. Every later
change MUST be a normal, explicit migration (``alembic revision --autogenerate``),
and this file should be frozen into explicit DDL before the first production release
(tracked as KNOWN_LIMITATIONS L-04).
"""
from alembic import op

from app.models import Base

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
