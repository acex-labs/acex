"""add job table

Jobs are what the backend hands to workers over RabbitMQ. The table, not the
broker, is the record of each job: a message carries only the job's id.

Revision ID: d4e8a1b2c3f5
Revises: c7d2e9f1a3b4
Create Date: 2026-10-07 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "d4e8a1b2c3f5"
down_revision: str | Sequence[str] | None = "c7d2e9f1a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATE = sa.Enum("queued", "running", "succeeded", "failed", "cancelled", name="jobstate")
_JSON = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "job",
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("subject_type", sa.String(), nullable=True),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("data", _JSON, nullable=True),
        sa.Column("result", _JSON, nullable=True),
        sa.Column("state", _STATE, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("claimed_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["job.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_type"), "job", ["type"], unique=False)
    op.create_index(op.f("ix_job_parent_id"), "job", ["parent_id"], unique=False)
    op.create_index(op.f("ix_job_state"), "job", ["state"], unique=False)
    op.create_index(op.f("ix_job_created_at"), "job", ["created_at"], unique=False)
    op.create_index("ix_job_subject", "job", ["subject_type", "subject_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_job_subject", table_name="job")
    op.drop_index(op.f("ix_job_created_at"), table_name="job")
    op.drop_index(op.f("ix_job_state"), table_name="job")
    op.drop_index(op.f("ix_job_parent_id"), table_name="job")
    op.drop_index(op.f("ix_job_type"), table_name="job")
    op.drop_table("job")
    _STATE.drop(op.get_bind(), checkfirst=True)
