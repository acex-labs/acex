"""a git repository can belong to one site, so that its ConfigMaps only apply to that site's nodes

Revision ID: b7d3f1a9c5e2
Revises: a6c2e8f4b1d3
Create Date: 2026-11-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "b7d3f1a9c5e2"
down_revision: str | Sequence[str] | None = "a6c2e8f4b1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("git_repository") as batch:
        batch.add_column(sa.Column("site", sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("git_repository") as batch:
        batch.drop_column("site")
