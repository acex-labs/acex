"""add the reported version and build to the agents

Collection and telemetry agents report the version of their package, the commit their image
was built from and the branch that build ran on in every ack, so the web interface can show
what runs.

Revision ID: b460f36be39a
Revises: a8c4e1f7b2d9
Create Date: 2026-10-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "b460f36be39a"
down_revision: str | Sequence[str] | None = "a8c4e1f7b2d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGENT_TABLES = ("collectionagent", "telemetryagent")


def upgrade() -> None:
    for table in AGENT_TABLES:
        op.add_column(table, sa.Column("agent_version", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        op.add_column(table, sa.Column("build_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        op.add_column(table, sa.Column("build_ref", sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    for table in reversed(AGENT_TABLES):
        op.drop_column(table, "build_ref")
        op.drop_column(table, "build_id")
        op.drop_column(table, "agent_version")
