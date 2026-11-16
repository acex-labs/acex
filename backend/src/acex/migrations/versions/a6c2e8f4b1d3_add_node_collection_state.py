"""add node collection state

What the collection agents found when they last tried each node: when, whether it worked, since when it has
failed and why. Nodes no agent has reported on yet have no row.

Revision ID: a6c2e8f4b1d3
Revises: f4b8d2a6c9e1
Create Date: 2026-11-16 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "a6c2e8f4b1d3"
down_revision: str | Sequence[str] | None = "f4b8d2a6c9e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "node_collection_state",
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("failing_since", sa.DateTime(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["node_id"], ["node.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("node_id"),
    )


def downgrade() -> None:
    op.drop_table("node_collection_state")
