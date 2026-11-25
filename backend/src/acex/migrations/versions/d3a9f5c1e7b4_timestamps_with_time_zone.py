"""timestamps keep the moment they stand for: `timestamp` columns become `timestamptz`

Every datetime column was created as `timestamp without time zone`, but the backend writes aware UTC values. PostgreSQL
turns such a value into the wall clock of the session's time zone when it stores it in a `timestamp` column, so on a
server that runs in Europe/Amsterdam every stored time was one hour ahead of UTC in winter and two in summer, and the
API then labelled it UTC.

A `timestamp` column is read in the session's zone when it becomes a `timestamptz`, which is the zone it was written in,
so every existing row gets the moment it always stood for. PostgreSQL only: SQLite has no time zones and the backend
already stores UTC there. The migration runs in the API's own session, so it reads the zone the API wrote with.

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


def _convert(bind, columns: list[tuple[str, str]], to: str) -> None:
    # `AT TIME ZONE` with the session's zone is what a plain cast does; spelled out so that the migration says
    # which zone it reads.
    for table, column in columns:
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE {to} '
            f"USING \"{column}\" AT TIME ZONE current_setting('TimeZone')"
        )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    columns = _present(bind, with_time_zone=False)
    logger.info(
        "Timestamps: %d column(s) to timestamptz, existing values read in time zone %s",
        len(columns),
        bind.exec_driver_sql("show timezone").scalar(),
    )
    _convert(bind, columns, "timestamptz")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    _convert(bind, _present(bind, with_time_zone=True), "timestamp")
