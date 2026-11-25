"""a git repository can have a webhook secret, so that a push syncs it at once

Revision ID: c9e4a2f6b8d1
Revises: b7d3f1a9c5e2
Create Date: 2026-11-25 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9e4a2f6b8d1"
down_revision: str | Sequence[str] | None = "b7d3f1a9c5e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("git_repository") as batch:
        batch.add_column(sa.Column("webhook_credential_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("git_repository") as batch:
        batch.drop_column("webhook_credential_id")
