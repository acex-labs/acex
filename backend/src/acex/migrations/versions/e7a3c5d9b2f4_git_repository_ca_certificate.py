"""git repositories can trust a CA of their own, for a host signed by an internal CA

Revision ID: e7a3c5d9b2f4
Revises: d2f8b4a6c1e9
Create Date: 2026-11-06 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "e7a3c5d9b2f4"
down_revision: str | Sequence[str] | None = "d2f8b4a6c1e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("git_repository") as batch:
        batch.add_column(sa.Column("ca_certificate", sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("git_repository") as batch:
        batch.drop_column("ca_certificate")
