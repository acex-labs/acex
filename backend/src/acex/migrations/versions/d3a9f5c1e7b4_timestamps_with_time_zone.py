"""timestamps keep the moment they stand for: `timestamp` columns become `timestamptz`

Every datetime column was created as `timestamp without time zone`, but the backend writes aware UTC values. PostgreSQL
turns such a value into the wall clock of the session's time zone when it stores it in a `timestamp` column, so on a
server that runs in a zone ahead of UTC every stored time was one or two hours ahead of UTC, and the API then labelled
it UTC.

A `timestamp` column is read in the session's zone when it becomes a `timestamptz`, which is the zone it was written in,
so the rows get the moment they stood for. PostgreSQL only: SQLite has no time zones and the backend already stores UTC
there. The migration runs in the API's own session, so it reads the zone the API wrote with.

One group of columns needs more. Until acex 6.20.0 (released 2026-09-22) the models of `node`, `device_config` and
`lldpneighbor` wrote `datetime.utcnow()`, a naive UTC value that PostgreSQL stores as it is: those rows hold the UTC
clock, not the server's. A deployment that took 6.20.0 on the day it came out has the UTC clock in every row stored
before 16:00 that day and the server's clock in every row after, with nothing in between, because the server's clock
is at least one hour ahead of UTC. The upgrade reads the first kind as UTC. A deployment that took 6.20.0 on another
day, or whose server runs behind UTC, has to change `_UTC_CLOCK_BEFORE` to the stored clock up to which its old rows
were written.

Revision ID: d3a9f5c1e7b4
Revises: c9e4a2f6b8d1
Create Date: 2026-11-25 16:00:00.000000

"""

import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3a9f5c1e7b4"
down_revision: str | Sequence[str] | None = "c9e4a2f6b8d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger(__name__)

#: Every datetime column the models had when this migration was written.
_COLUMNS: tuple[tuple[str, str], ...] = (
    ("cve", "published"),
    ("cve", "last_modified"),
    ("cve", "created_at"),
    ("cve", "updated_at"),
    ("cve_state", "updated_at"),
    ("device_config", "created_at"),
    ("device_config", "last_collected_at"),
    ("enabled_hardware_model", "enabled_at"),
    ("externalvalue", "resolved_at"),
    ("git_repository", "last_checked_at"),
    ("git_repository", "last_synced_at"),
    ("git_repository", "created_at"),
    ("git_repository", "updated_at"),
    ("job", "created_at"),
    ("job", "run_at"),
    ("job", "started_at"),
    ("job", "finished_at"),
    ("lldpneighbor", "collected_at"),
    ("node", "created_at"),
    ("node", "updated_at"),
    ("node_collection_state", "last_attempt_at"),
    ("node_collection_state", "last_success_at"),
    ("node_collection_state", "failing_since"),
    ("software_policy", "updated_at"),
    ("sync_state", "last_sync"),
    ("workflow", "created_at"),
    ("workflow", "updated_at"),
    ("ztp_dhcp_scope", "updated_at"),
    ("ztp_discovery", "reviewed_at"),
    ("ztp_discovery", "created_at"),
    ("ztp_method", "updated_at"),
    ("ztp_vendor_class", "updated_at"),
)

#: The columns whose old rows hold the UTC clock (see above). Every other column was written as an aware value from the
#: day its table was made, so all of its rows hold the server's clock.
_LEGACY: frozenset[tuple[str, str]] = frozenset(
    {
        ("node", "created_at"),
        ("node", "updated_at"),
        ("device_config", "created_at"),
        ("lldpneighbor", "collected_at"),
    }
)

#: A stored value of a legacy column before this is the UTC clock; from it, the server's clock.
_UTC_CLOCK_BEFORE = "2026-09-22 16:00:00"
#: The same boundary after the conversion, where the value is a moment and not a clock: a moment before this was
#: stored as the UTC clock and goes back to it when the migration is undone. It lies between the last old row and the
#: first new one, like the boundary above, and is an hour earlier because the server's clock is one or two hours ahead.
_UTC_MOMENT_BEFORE = "2026-09-22 15:00:00+00"


def _present(bind, with_time_zone: bool) -> list[tuple[str, str]]:
    """The listed columns that exist and are (not) `timestamptz` at the moment."""
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    found = []
    for table, column in _COLUMNS:
        if table not in tables:
            continue
        for described in inspector.get_columns(table):
            if described["name"] == column and bool(getattr(described["type"], "timezone", False)) == with_time_zone:
                found.append((table, column))
    return found


def _reading(table: str, column: str, to: str) -> str:
    """The expression that gives the column its new value."""
    # `AT TIME ZONE` with the session's zone is what a plain cast does; spelled out so that the migration says
    # which zone it reads.
    server = f"\"{column}\" AT TIME ZONE current_setting('TimeZone')"
    if (table, column) not in _LEGACY:
        return server
    utc = f"\"{column}\" AT TIME ZONE 'UTC'"
    if to == "timestamptz":
        return f"CASE WHEN \"{column}\" < timestamp '{_UTC_CLOCK_BEFORE}' THEN {utc} ELSE {server} END"
    return f"CASE WHEN \"{column}\" < timestamptz '{_UTC_MOMENT_BEFORE}' THEN {utc} ELSE {server} END"


def _convert(columns: list[tuple[str, str]], to: str) -> None:
    for table, column in columns:
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE {to} USING {_reading(table, column, to)}')


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    columns = _present(bind, with_time_zone=False)
    logger.info(
        "Timestamps: %d column(s) to timestamptz, rows read in time zone %s, but as UTC before %s in %d of them",
        len(columns),
        bind.exec_driver_sql("show timezone").scalar(),
        _UTC_CLOCK_BEFORE,
        len(_LEGACY & set(columns)),
    )
    _convert(columns, "timestamptz")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    _convert(_present(bind, with_time_zone=True), "timestamp")
