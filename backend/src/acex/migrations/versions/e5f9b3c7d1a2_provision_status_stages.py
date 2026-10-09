"""provision_status: ZTP stages named after who is being waited on

pending becomes awaiting_device, awaiting_approval is added, and bootstrapping is
dropped: before discovery ACEX does not know which node a device is, so that stage
is tracked on the discovery job instead.

The enum type is rebuilt rather than altered value by value, so this works
whatever values a database's type holds, including databases that ran an earlier
draft of this change.

Revision ID: e5f9b3c7d1a2
Revises: d4e8a1b2c3f5
Create Date: 2026-10-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f9b3c7d1a2"
down_revision: str | Sequence[str] | None = "d4e8a1b2c3f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = (
    "unprovisioned",
    "adopted",
    "awaiting_device",
    "awaiting_approval",
    "provisioning",
    "provisioned",
    "failed",
)
_OLD = ("unprovisioned", "adopted", "pending", "bootstrapping", "provisioning", "provisioned", "failed")

#: Old value -> new value. A bootstrapping device has not been discovered yet.
_UPGRADE = {"pending": "awaiting_device", "bootstrapping": "awaiting_device"}
#: New value -> old value. A device awaiting approval was reachable, as bootstrapping meant.
_DOWNGRADE = {"awaiting_device": "pending", "awaiting_approval": "bootstrapping"}

_RULE_TABLES = ("collectionagentmatchrule", "telemetryagentmatchrule")


def _case(mapping: dict[str, str]) -> str:
    whens = " ".join(f"WHEN '{old}' THEN '{new}'" for old, new in mapping.items())
    return f"CASE provision_status::text {whens} ELSE provision_status::text END"


def _migrate(values: tuple[str, ...], mapping: dict[str, str]) -> None:
    bind = op.get_bind()
    # Agent match rules store provision_status as a plain string.
    for table in _RULE_TABLES:
        for old, new in mapping.items():
            op.execute(sa.text(f"UPDATE {table} SET provision_status = '{new}' WHERE provision_status = '{old}'"))

    if bind.dialect.name != "postgresql":
        # SQLite stores the enum as a plain string.
        for old, new in mapping.items():
            op.execute(sa.text(f"UPDATE node SET provision_status = '{new}' WHERE provision_status = '{old}'"))
        return

    op.execute(sa.text("ALTER TYPE nodeprovisionstatus RENAME TO nodeprovisionstatus_old"))
    sa.Enum(*values, name="nodeprovisionstatus").create(bind)
    op.execute(
        sa.text(
            "ALTER TABLE node ALTER COLUMN provision_status TYPE nodeprovisionstatus "
            f"USING ({_case(mapping)})::nodeprovisionstatus"
        )
    )
    op.execute(sa.text("DROP TYPE nodeprovisionstatus_old"))


def upgrade() -> None:
    _migrate(_NEW, _UPGRADE)


def downgrade() -> None:
    _migrate(_OLD, _DOWNGRADE)
