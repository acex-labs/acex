"""add btree index on logicalnode.hostname for sorting

Revision ID: d8e3f0a2b5c7
Revises: c7d2e9f1a3b4
Create Date: 2026-10-02 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "d8e3f0a2b5c7"
down_revision: str | Sequence[str] | None = "c7d2e9f1a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_logicalnode_hostname ON logicalnode (hostname)"))


def downgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return
    op.execute(text("DROP INDEX IF EXISTS ix_logicalnode_hostname"))
