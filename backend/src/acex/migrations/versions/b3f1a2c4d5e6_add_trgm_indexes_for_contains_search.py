"""add pg_trgm extension and GIN indexes for contains search

Revision ID: b3f1a2c4d5e6
Revises: a9222fcfea74
Create Date: 2026-09-15 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "b3f1a2c4d5e6"
down_revision: str | Sequence[str] | None = "a9222fcfea74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = [
    ("ix_site_name_trgm", "site", "name"),
    ("ix_site_display_name_trgm", "site", "display_name"),
    ("ix_asset_vendor_trgm", "asset", "vendor"),
    ("ix_asset_hardware_model_trgm", "asset", "hardware_model"),
    ("ix_asset_serial_number_trgm", "asset", "serial_number"),
    ("ix_logicalnode_hostname_trgm", "logicalnode", "hostname"),
]


def upgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return
    conn = op.get_bind()
    row = conn.execute(text("SELECT 1 FROM pg_available_extensions WHERE name = 'pg_trgm'")).fetchone()
    if not row:
        return
    op.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    for index_name, table, column in _INDEXES:
        op.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} USING GIN ({column} gin_trgm_ops)"))


def downgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return
    for index_name, _table, _ in _INDEXES:
        op.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
