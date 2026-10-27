"""add CVE tables

Revision ID: d8f3b1a6c9e2
Revises: c3f7a9e1d5b8
Create Date: 2026-10-26 10:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlmodel.sql.sqltypes import AutoString

revision: str = "d8f3b1a6c9e2"
down_revision: str | Sequence[str] | None = "c3f7a9e1d5b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cve",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cve_id", AutoString(), nullable=False),
        sa.Column("published", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", AutoString(), nullable=True),
        sa.Column("cvss_score", sa.Float(), nullable=True),
        sa.Column("raw", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cve_cve_id"), "cve", ["cve_id"], unique=True)
    op.create_index(op.f("ix_cve_published"), "cve", ["published"], unique=False)
    op.create_index(op.f("ix_cve_last_modified"), "cve", ["last_modified"], unique=False)
    op.create_index(op.f("ix_cve_created_at"), "cve", ["created_at"], unique=False)

    op.create_table(
        "cve_state",
        sa.Column("cve_id", AutoString(), nullable=False),
        sa.Column("status", AutoString(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cve_id"], ["cve.cve_id"]),
        sa.PrimaryKeyConstraint("cve_id"),
    )
    op.create_table(
        "sync_state",
        sa.Column("key", AutoString(), nullable=False),
        sa.Column("last_sync", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("sync_state")
    op.drop_table("cve_state")
    op.drop_index(op.f("ix_cve_created_at"), table_name="cve")
    op.drop_index(op.f("ix_cve_last_modified"), table_name="cve")
    op.drop_index(op.f("ix_cve_published"), table_name="cve")
    op.drop_index(op.f("ix_cve_cve_id"), table_name="cve")
    op.drop_table("cve")
