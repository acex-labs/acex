"""add ztp_vendor_class and ztp_dhcp_scope tables, and the default ZTP method

What the ZTP DHCP config is rendered from: the DHCP vendor classes devices send,
matched exactly or by prefix and each mapped to the ZTP method it bootstraps
with (or to none until an administrator maps it), the method devices matching
none of them get, and the IPv4 networks addresses are handed out in.

Revision ID: c3f7a9e1d5b8
Revises: b8e2d4f6a1c3
Create Date: 2026-10-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "c3f7a9e1d5b8"
down_revision: str | Sequence[str] | None = "b8e2d4f6a1c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ztp_vendor_class",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vendor_class", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("match", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="exact"),
        sa.Column("method", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vendor_class"),
    )
    op.create_table(
        "ztp_dhcp_scope",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("network", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("pool_start", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("pool_end", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("gateway", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("dns_servers", sa.JSON(), nullable=False),
        sa.Column("domain_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("network"),
    )
    op.add_column("ztp_method", sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("ztp_method", "is_default")
    op.drop_table("ztp_dhcp_scope")
    op.drop_table("ztp_vendor_class")
