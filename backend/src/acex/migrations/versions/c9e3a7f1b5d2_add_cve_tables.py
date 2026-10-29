"""add CVE records, workflow state and sync checkpoints

Revision ID: c9e3a7f1b5d2
Revises: b460f36be39a
Create Date: 2026-10-29 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c9e3a7f1b5d2"
down_revision: str | Sequence[str] | None = "b460f36be39a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cve",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cve_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("published", sa.DateTime(), nullable=True),
        sa.Column("last_modified", sa.DateTime(), nullable=True),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("cvss_score", sa.Float(), nullable=True),
        sa.Column("base_severity", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("raw", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cve_cve_id"), "cve", ["cve_id"], unique=True)
    for column in ("published", "last_modified", "created_at"):
        op.create_index(op.f(f"ix_cve_{column}"), "cve", [column], unique=False)
    op.create_table(
        "cve_state",
        sa.Column("cve_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["cve_id"], ["cve.cve_id"]),
        sa.PrimaryKeyConstraint("cve_id"),
    )
    op.create_table(
        "sync_state",
        sa.Column("key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("last_sync", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("sync_state")
    op.drop_table("cve_state")
    for column in ("created_at", "last_modified", "published", "cve_id"):
        op.drop_index(op.f(f"ix_cve_{column}"), table_name="cve")
    op.drop_table("cve")
