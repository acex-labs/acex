"""add topology_position table

The shared layout of the topology page: where an item (a node, a site, a region) was placed in a container (the
nodes of a site, the sites of a region, the boxes around them), relative to the container. One row per item and
container, so people moving different items do not overwrite each other.

Revision ID: a7c3e9f1b5d2
Revises: d3a9f5c1e7b4
Create Date: 2026-11-27 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "a7c3e9f1b5d2"
down_revision: str | Sequence[str] | None = "d3a9f5c1e7b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "topology_position",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("container", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("item", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("container", "item", name="uq_topology_position_container_item"),
    )
    op.create_index(op.f("ix_topology_position_container"), "topology_position", ["container"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_topology_position_container"), table_name="topology_position")
    op.drop_table("topology_position")
