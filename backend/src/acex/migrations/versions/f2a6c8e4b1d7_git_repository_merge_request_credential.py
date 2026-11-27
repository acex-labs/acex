"""a git repository can have a token that merge requests are sent with

Revision ID: f2a6c8e4b1d7
Revises: d3a9f5c1e7b4
Create Date: 2026-11-27 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a6c8e4b1d7"
down_revision: str | Sequence[str] | None = "d3a9f5c1e7b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("git_repository") as batch:
        batch.add_column(sa.Column("merge_request_credential_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("git_repository") as batch:
        batch.drop_column("merge_request_credential_id")
