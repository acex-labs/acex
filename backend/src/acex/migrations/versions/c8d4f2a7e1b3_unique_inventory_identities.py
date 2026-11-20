"""one asset per serial number, one logical node per hostname, one node instance per logical node and per asset

Unique indexes behind the checks the inventory services make before they write. Serial numbers and hostnames
are compared trimmed and ignoring case, so their indexes are on `lower(trim(column))`. A node instance's asset
is its `asset_ref_id` of its `asset_ref_type`, since an asset and a cluster can have the same id.

Migrations run at startup, so this one must never stop it: an index is only created when the data has no
duplicates. Otherwise the duplicates are logged with the statement to run once they are sorted out, and the
index is left out. The services refuse new duplicates either way.

On SQLite a later `batch_alter_table` on `asset` or `logicalnode` drops the expression indexes (Alembic cannot
reflect them); create them again at the end of such a migration.

Revision ID: c8d4f2a7e1b3
Revises: f4b8d2a6c9e1
Create Date: 2026-11-17 13:00:00.000000

"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

import sqlalchemy as sa
from alembic import op

revision: str = "c8d4f2a7e1b3"
down_revision: str | Sequence[str] | None = "f4b8d2a6c9e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = logging.getLogger("acex.migrations")

#: How many duplicates a warning lists.
_SHOWN = 50


@dataclass(frozen=True)
class _Index:
    name: str
    table: str
    #: What the index is on: plain columns, or SQL expressions of them.
    keys: tuple[str, ...]
    #: The stored columns the keys are made from, shown next to a duplicate when the keys are expressions.
    columns: tuple[str, ...]
    #: What a duplicate is, for the warning.
    what: str

    @property
    def on(self) -> str:
        return ", ".join(self.keys)

    @property
    def is_expression(self) -> bool:
        return self.keys != self.columns


_INDEXES = (
    _Index(
        "uq_asset_serial_number_norm",
        "asset",
        ("lower(trim(serial_number))",),
        ("serial_number",),
        "assets with one serial",
    ),
    _Index(
        "uq_logicalnode_hostname_norm",
        "logicalnode",
        ("lower(trim(hostname))",),
        ("hostname",),
        "logical nodes with one hostname",
    ),
    _Index(
        "uq_node_logical_node_id",
        "node",
        ("logical_node_id",),
        ("logical_node_id",),
        "node instances of one logical node",
    ),
    _Index(
        "uq_node_asset_ref",
        "node",
        ("asset_ref_type", "asset_ref_id"),
        ("asset_ref_type", "asset_ref_id"),
        "node instances on one asset or cluster",
    ),
)


def _duplicates(bind, index: _Index) -> list[tuple[tuple, list[tuple[int, tuple]]]]:
    """Every key held by more than one row, with the id (and stored values) of each of those rows."""
    keys = index.on
    selected = ["id", *index.keys] + (list(index.columns) if index.is_expression else [])
    rows = bind.execute(
        sa.text(
            f"SELECT {', '.join(selected)} FROM {index.table}"
            f" WHERE ({keys}) IN (SELECT {keys} FROM {index.table} GROUP BY {keys} HAVING COUNT(*) > 1)"
            f" ORDER BY {keys}, id"
        )
    ).all()
    width = len(index.keys)
    groups: dict[tuple, list[tuple[int, tuple]]] = {}
    for row in rows:
        groups.setdefault(tuple(row[1 : 1 + width]), []).append((row[0], tuple(row[1 + width :])))
    return list(groups.items())


def _warn_duplicates(index: _Index, groups) -> None:
    lines = [
        f"  {' '.join(str(part) for part in key)}: "
        + ", ".join(
            f"id {row_id}" + (f" ({', '.join(map(repr, stored))})" if stored else "") for row_id, stored in rows
        )
        for key, rows in groups[:_SHOWN]
    ]
    if len(groups) > _SHOWN:
        lines.append(f"  ... and {len(groups) - _SHOWN} more")
    log.warning(
        "Unique index %s was not created: %d duplicate group(s) of %s.\n%s\n"
        "Sort out the duplicates, then run:\n  CREATE UNIQUE INDEX %s ON %s (%s);\n"
        "The API refuses new duplicates in the meantime.",
        index.name,
        len(groups),
        index.what,
        "\n".join(lines),
        index.name,
        index.table,
        index.on,
    )


def upgrade() -> None:
    bind = op.get_bind()
    for index in _INDEXES:
        groups = _duplicates(bind, index)
        if groups:
            _warn_duplicates(index, groups)
            continue
        try:
            # A savepoint: on PostgreSQL a failed statement would otherwise abort the whole migration.
            with bind.begin_nested():
                op.create_index(
                    index.name,
                    index.table,
                    [key if key.isidentifier() else sa.text(key) for key in index.keys],
                    unique=True,
                    if_not_exists=True,
                )
        except sa.exc.DBAPIError:
            # A duplicate that was added between the check and the index.
            log.warning(
                "Unique index %s was not created: the table changed while it was being built.",
                index.name,
                exc_info=True,
            )


def downgrade() -> None:
    for index in reversed(_INDEXES):
        op.drop_index(index.name, table_name=index.table, if_exists=True)
