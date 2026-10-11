"""ztp_discovery: approved as an asset, no longer matched to a node

Approving a discovery now trusts the device's identity and creates or updates
the asset with its serial; nodes are left alone. Discoveries approved before
this get the asset of the node they were matched to.

Revision ID: a3c9e5f1b7d2
Revises: d4e8a2c6f0b1
Create Date: 2026-10-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3c9e5f1b7d2"
down_revision: str | Sequence[str] | None = "d4e8a2c6f0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ztp_discovery", sa.Column("asset_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_ztp_discovery_asset_id"), "ztp_discovery", ["asset_id"], unique=False)
    op.create_foreign_key(
        "ztp_discovery_asset_id_fkey", "ztp_discovery", "asset", ["asset_id"], ["id"], ondelete="SET NULL"
    )
    op.execute(
        sa.text(
            "UPDATE ztp_discovery SET asset_id = ("
            "SELECT node.asset_ref_id FROM node "
            "WHERE node.id = ztp_discovery.node_id AND node.asset_ref_type = 'asset'"
            ") WHERE review_status = 'approved'"
        )
    )
    op.drop_index(op.f("ix_ztp_discovery_node_id"), table_name="ztp_discovery")
    op.drop_column("ztp_discovery", "node_id")


def downgrade() -> None:
    op.add_column("ztp_discovery", sa.Column("node_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_ztp_discovery_node_id"), "ztp_discovery", ["node_id"], unique=False)
    op.create_foreign_key(
        "ztp_discovery_node_id_fkey", "ztp_discovery", "node", ["node_id"], ["id"], ondelete="SET NULL"
    )
    op.drop_constraint("ztp_discovery_asset_id_fkey", "ztp_discovery", type_="foreignkey")
    op.drop_index(op.f("ix_ztp_discovery_asset_id"), table_name="ztp_discovery")
    op.drop_column("ztp_discovery", "asset_id")
