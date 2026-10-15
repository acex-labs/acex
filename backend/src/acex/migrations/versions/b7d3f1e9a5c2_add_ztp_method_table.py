"""add ztp_method table

One row per ZTP method with what an administrator has chosen for it, to begin
with the NED discovery uses.

Revision ID: b7d3f1e9a5c2
Revises: a1c5e7f9b2d4
Create Date: 2026-10-09 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "b7d3f1e9a5c2"
down_revision: str | Sequence[str] | None = "a1c5e7f9b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = op.create_table(
        "ztp_method",
        sa.Column("method", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ned", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("method"),
    )
    # The methods that exist at this revision. Later ones get their row when the backend starts.
    op.bulk_insert(table, [{"method": "cisco_iosxe_python"}])


def downgrade() -> None:
    op.drop_table("ztp_method")
