"""add ztp_discovery table

One row per ZTP discovery: the device at an IP says it is a serial number. An
administrator approves or rejects it before the node it matched is provisioned.

Revision ID: f6a0c4d8e2b3
Revises: e5f9b3c7d1a2
Create Date: 2026-10-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "f6a0c4d8e2b3"
down_revision: str | Sequence[str] | None = "e5f9b3c7d1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ztp_discovery",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("source_ip", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("serial_number", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("vendor", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("hardware_model", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("os", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("os_version", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("node_id", sa.Integer(), nullable=True),
        sa.Column("review_status", sa.String(), nullable=False),
        sa.Column("reviewed_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["job.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["node_id"], ["node.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index(op.f("ix_ztp_discovery_source_ip"), "ztp_discovery", ["source_ip"], unique=False)
    op.create_index(op.f("ix_ztp_discovery_serial_number"), "ztp_discovery", ["serial_number"], unique=False)
    op.create_index(op.f("ix_ztp_discovery_node_id"), "ztp_discovery", ["node_id"], unique=False)
    op.create_index(op.f("ix_ztp_discovery_review_status"), "ztp_discovery", ["review_status"], unique=False)
    op.create_index(op.f("ix_ztp_discovery_created_at"), "ztp_discovery", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ztp_discovery_created_at"), table_name="ztp_discovery")
    op.drop_index(op.f("ix_ztp_discovery_review_status"), table_name="ztp_discovery")
    op.drop_index(op.f("ix_ztp_discovery_node_id"), table_name="ztp_discovery")
    op.drop_index(op.f("ix_ztp_discovery_serial_number"), table_name="ztp_discovery")
    op.drop_index(op.f("ix_ztp_discovery_source_ip"), table_name="ztp_discovery")
    op.drop_table("ztp_discovery")
