"""add software policy and enabled hardware models

The software versions approved per vendor or hardware model, one of them golden, and the declared hardware
models the installation runs. The models of the assets already in the inventory start out enabled.

Revision ID: f4b8d2a6c9e1
Revises: e7a3c5d9b2f4
Create Date: 2026-11-10 12:00:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
import sqlmodel
from acex_devkit import device_types
from alembic import op

revision: str = "f4b8d2a6c9e1"
down_revision: str | Sequence[str] | None = "e7a3c5d9b2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "software_policy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vendor", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("hardware_model", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("os", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("os_version", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("golden", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_software_policy_vendor"), "software_policy", ["vendor"], unique=False)

    enabled = op.create_table(
        "enabled_hardware_model",
        sa.Column("hardware_model", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("enabled_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("enabled_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("hardware_model"),
    )
    # The models of the assets already in the inventory, as the devkit declares them; undeclared ones are left out.
    models = set()
    for (model,) in op.get_bind().execute(sa.text("SELECT DISTINCT hardware_model FROM asset")):
        device = device_types.get(model) if model else None
        if device is not None:
            models.add(next(m for m in device.models if m.casefold() == model.casefold()))
    now = datetime.now(UTC)
    op.bulk_insert(
        enabled, [{"hardware_model": m, "enabled_by": "inventory", "enabled_at": now} for m in sorted(models)]
    )


def downgrade() -> None:
    op.drop_table("enabled_hardware_model")
    op.drop_index(op.f("ix_software_policy_vendor"), table_name="software_policy")
    op.drop_table("software_policy")
