"""add pg_trgm extension and GIN indexes for contains search

Revision ID: b3f1a2c4d5e6
Revises: a9222fcfea74
Create Date: 2026-09-15 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = "b3f1a2c4d5e6"
down_revision: str | Sequence[str] | None = "a9222fcfea74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = [
    ("ix_site_name_trgm",         "site",        "name"),
    ("ix_site_display_name_trgm", "site",        "display_name"),
    ("ix_asset_vendor_trgm",      "asset",       "vendor"),
    ("ix_asset_hardware_model_trgm", "asset",    "hardware_model"),
    ("ix_asset_serial_number_trgm",  "asset",    "serial_number"),
    ("ix_logicalnode_hostname_trgm", "logicalnode", "hostname"),
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for index_name, table, column in _INDEXES:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON {table} USING GIN ({column} gin_trgm_ops)"
        )


def downgrade() -> None:
    for index_name, table, _ in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
