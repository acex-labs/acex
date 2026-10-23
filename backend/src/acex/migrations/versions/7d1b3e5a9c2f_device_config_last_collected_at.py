"""device_config.last_collected_at: when the node was last polled

Revision ID: 7d1b3e5a9c2f
Revises: c3f7a9e1d5b8
Create Date: 2026-10-22 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7d1b3e5a9c2f"
down_revision: str | Sequence[str] | None = "c3f7a9e1d5b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("device_config", sa.Column("last_collected_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("device_config", "last_collected_at")
