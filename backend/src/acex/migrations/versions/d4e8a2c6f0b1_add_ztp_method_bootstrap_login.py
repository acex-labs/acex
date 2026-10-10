"""add the bootstrap login to ztp_method

The temporary username and password a ZTP bootstrap gives a device, for
discovery to log in with until onboarding rotates it.

Revision ID: d4e8a2c6f0b1
Revises: b7d3f1e9a5c2
Create Date: 2026-10-09 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "d4e8a2c6f0b1"
down_revision: str | Sequence[str] | None = "b7d3f1e9a5c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ztp_method", sa.Column("bootstrap_username", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column("ztp_method", sa.Column("bootstrap_password", sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    op.drop_column("ztp_method", "bootstrap_password")
    op.drop_column("ztp_method", "bootstrap_username")
