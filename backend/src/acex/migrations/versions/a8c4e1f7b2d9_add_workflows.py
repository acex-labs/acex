"""add workflows, and jobs that are scheduled or paused

A workflow holds its steps on a graph. A run is a job that pauses between steps in evaluate mode; a wait in
it is a job scheduled to run later, kept in the jobs table until its time comes.

Revision ID: a8c4e1f7b2d9
Revises: 7d1b3e5a9c2f
Create Date: 2026-10-24 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "a8c4e1f7b2d9"
down_revision: str | Sequence[str] | None = "7d1b3e5a9c2f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "workflow",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("graph", _JSON, nullable=False),
        sa.Column("max_rounds", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_name"), "workflow", ["name"], unique=False)
    with op.batch_alter_table("job") as batch:
        batch.add_column(sa.Column("run_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_job_run_at"), "job", ["run_at"], unique=False)
    # Elsewhere the state is a plain string. Postgres won't add an enum value inside a transaction.
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE jobstate ADD VALUE IF NOT EXISTS 'paused'")
            op.execute("ALTER TYPE jobstate ADD VALUE IF NOT EXISTS 'scheduled'")


def downgrade() -> None:
    # Postgres can't drop an enum value; jobs left in one would no longer read, so they end as failed.
    op.execute("UPDATE job SET state = 'failed' WHERE state IN ('paused', 'scheduled')")
    op.drop_index(op.f("ix_job_run_at"), table_name="job")
    with op.batch_alter_table("job") as batch:
        batch.drop_column("run_at")
    op.drop_index(op.f("ix_workflow_name"), table_name="workflow")
    op.drop_table("workflow")
