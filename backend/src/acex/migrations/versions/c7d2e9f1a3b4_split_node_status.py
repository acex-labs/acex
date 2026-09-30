"""split node.status into admin_status and provision_status

node.status becomes admin_status (operator intent: planned/active/decommissioned;
the old "init" value is dropped in favour of provision_status). provision_status
tracks where the device is in the provisioning lifecycle. Agent match rules get
the same two fields.

Existing data: active nodes are treated as brownfield (adopted), everything else
as unprovisioned; init maps to planned.

Revision ID: c7d2e9f1a3b4
Revises: b3f1a2c4d5e6
Create Date: 2026-09-30 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "c7d2e9f1a3b4"
down_revision: str | Sequence[str] | None = "b3f1a2c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_STATUS = sa.Enum("planned", "init", "active", "decommissioned", name="nodestatus")
_ADMIN_STATUS = sa.Enum("planned", "active", "decommissioned", name="nodeadminstatus")
_PROVISION_STATUS = sa.Enum(
    "unprovisioned",
    "adopted",
    "pending",
    "bootstrapping",
    "provisioning",
    "provisioned",
    "failed",
    name="nodeprovisionstatus",
)
_RULE_TABLES = ("collectionagentmatchrule", "telemetryagentmatchrule")


def upgrade() -> None:
    bind = op.get_bind()
    _ADMIN_STATUS.create(bind, checkfirst=True)
    _PROVISION_STATUS.create(bind, checkfirst=True)

    with op.batch_alter_table("node") as batch:
        batch.add_column(sa.Column("admin_status", _ADMIN_STATUS, nullable=True))
        batch.add_column(sa.Column("provision_status", _PROVISION_STATUS, nullable=True))

    # Postgres needs explicit casts between enum types; SQLite stores them as plain strings.
    pg = bind.dialect.name == "postgresql"
    admin = "(CASE WHEN status = 'init' THEN 'planned' ELSE CAST(status AS VARCHAR) END)"
    provision = "(CASE WHEN status = 'active' THEN 'adopted' ELSE 'unprovisioned' END)"
    if pg:
        admin += "::nodeadminstatus"
        provision += "::nodeprovisionstatus"
    op.execute(sa.text(f"UPDATE node SET admin_status = {admin}, provision_status = {provision}"))

    with op.batch_alter_table("node") as batch:
        batch.alter_column("admin_status", existing_type=_ADMIN_STATUS, nullable=False)
        batch.alter_column("provision_status", existing_type=_PROVISION_STATUS, nullable=False)
        batch.drop_column("status")
    _OLD_STATUS.drop(bind, checkfirst=True)

    for table in _RULE_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("status", new_column_name="admin_status")
            batch.add_column(sa.Column("provision_status", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        op.execute(sa.text(f"UPDATE {table} SET admin_status = 'planned' WHERE admin_status = 'init'"))


def downgrade() -> None:
    bind = op.get_bind()

    for table in _RULE_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_column("provision_status")
            batch.alter_column("admin_status", new_column_name="status")

    _OLD_STATUS.create(bind, checkfirst=True)
    with op.batch_alter_table("node") as batch:
        batch.add_column(sa.Column("status", _OLD_STATUS, nullable=True))
    cast = "admin_status::text::nodestatus" if bind.dialect.name == "postgresql" else "admin_status"
    op.execute(sa.text(f"UPDATE node SET status = {cast}"))
    with op.batch_alter_table("node") as batch:
        batch.alter_column("status", existing_type=_OLD_STATUS, nullable=False)
        batch.drop_column("provision_status")
        batch.drop_column("admin_status")
    _PROVISION_STATUS.drop(bind, checkfirst=True)
    _ADMIN_STATUS.drop(bind, checkfirst=True)
