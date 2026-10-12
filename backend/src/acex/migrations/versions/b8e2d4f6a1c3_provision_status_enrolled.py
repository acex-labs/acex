"""provision_status: enrolled replaces awaiting_device and awaiting_approval

Being in ZTP is now recorded on the node, so a node can leave it again. An
enrolled node's stage (awaiting device, awaiting approval, ready) comes from its
asset's discoveries. Planned, unprovisioned nodes were in the pipeline before
this, so they are enrolled. The status a node had when it was enrolled is kept
in ztp_previous_status, to return to if ZTP is cancelled.

Revision ID: b8e2d4f6a1c3
Revises: a3c9e5f1b7d2
Create Date: 2026-10-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8e2d4f6a1c3"
down_revision: str | Sequence[str] | None = "a3c9e5f1b7d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = ("unprovisioned", "adopted", "enrolled", "provisioning", "provisioned", "failed")
_OLD = (
    "unprovisioned",
    "adopted",
    "awaiting_device",
    "awaiting_approval",
    "provisioning",
    "provisioned",
    "failed",
)

_UPGRADE = {"awaiting_device": "enrolled", "awaiting_approval": "enrolled"}
_DOWNGRADE = {"enrolled": "awaiting_device"}

_RULE_TABLES = ("collectionagentmatchrule", "telemetryagentmatchrule")


def _case(column: str, mapping: dict[str, str]) -> str:
    whens = " ".join(f"WHEN '{old}' THEN '{new}'" for old, new in mapping.items())
    return f"CASE {column}::text {whens} ELSE {column}::text END"


def _migrate(values: tuple[str, ...], mapping: dict[str, str], columns: tuple[str, ...]) -> None:
    bind = op.get_bind()
    # Agent match rules store provision_status as a plain string.
    for table in _RULE_TABLES:
        for old, new in mapping.items():
            op.execute(sa.text(f"UPDATE {table} SET provision_status = '{new}' WHERE provision_status = '{old}'"))

    if bind.dialect.name != "postgresql":
        # SQLite stores the enum as a plain string.
        for column in columns:
            for old, new in mapping.items():
                op.execute(sa.text(f"UPDATE node SET {column} = '{new}' WHERE {column} = '{old}'"))
        return

    op.execute(sa.text("ALTER TYPE nodeprovisionstatus RENAME TO nodeprovisionstatus_old"))
    sa.Enum(*values, name="nodeprovisionstatus").create(bind)
    for column in columns:
        op.execute(
            sa.text(
                f"ALTER TABLE node ALTER COLUMN {column} TYPE nodeprovisionstatus "
                f"USING ({_case(column, mapping)})::nodeprovisionstatus"
            )
        )
    op.execute(sa.text("DROP TYPE nodeprovisionstatus_old"))


def upgrade() -> None:
    _migrate(_NEW, _UPGRADE, ("provision_status",))
    op.add_column(
        "node",
        sa.Column(
            "ztp_previous_status",
            sa.Enum(*_NEW, name="nodeprovisionstatus", create_type=False),
            nullable=True,
        ),
    )
    # Enrolled nodes came from a claim of a planned node, which was unprovisioned before.
    op.execute(sa.text("UPDATE node SET ztp_previous_status = 'unprovisioned' WHERE provision_status = 'enrolled'"))
    op.execute(
        sa.text(
            "UPDATE node SET provision_status = 'enrolled', ztp_previous_status = 'unprovisioned' "
            "WHERE provision_status = 'unprovisioned' AND admin_status = 'planned' AND asset_ref_type = 'asset'"
        )
    )


def downgrade() -> None:
    op.drop_column("node", "ztp_previous_status")
    _migrate(_OLD, _DOWNGRADE, ("provision_status",))
