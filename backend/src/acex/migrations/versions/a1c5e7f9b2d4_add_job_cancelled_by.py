"""job.cancelled_by: who cancelled a job

Revision ID: a1c5e7f9b2d4
Revises: f6a0c4d8e2b3
Create Date: 2026-10-09 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c5e7f9b2d4"
down_revision: str | Sequence[str] | None = "f6a0c4d8e2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("job", sa.Column("cancelled_by", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("job", "cancelled_by")
