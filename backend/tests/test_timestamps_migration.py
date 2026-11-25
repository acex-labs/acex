"""The timestamp migration: PostgreSQL columns keep the moment they stand for, whatever zone the server runs in.

The backend writes aware UTC values. Into a `timestamp` column PostgreSQL stores them as the wall clock of the session's
zone, and the API then called that UTC, so a server in Europe/Amsterdam showed every time one hour ahead in winter and
two in summer. The migration makes the columns `timestamptz` and reads the old rows in the zone they were written in,
except the rows that the older models wrote as the UTC clock (`node`, `device_config` and `lldpneighbor`, before
2026-09-22).

The SQLite tests always run. The PostgreSQL ones run when `ACEX_TEST_POSTGRES_URL` names a server that may create
and drop a database, for example `postgresql+psycopg2://postgres:postgres@localhost:55432/postgres`.
"""

import importlib.util
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from acex.database import Connection, DatabaseManager
from acex.models.device_config import StoredDeviceConfig
from acex.models.git_repository import GitRepositoryRow
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlmodel import Session

MIGRATIONS = Path(__file__).parent.parent / "src/acex/migrations"
MIGRATION = MIGRATIONS / "versions/d3a9f5c1e7b4_timestamps_with_time_zone.py"

WINTER = datetime(2026, 11, 25, 13, 13, 54, 427564, tzinfo=UTC)  # Amsterdam is UTC+1
SUMMER = datetime(2026, 7, 1, 10, 0, 0, tzinfo=UTC)  # Amsterdam is UTC+2

POSTGRES_URL = os.environ.get("ACEX_TEST_POSTGRES_URL")
needs_postgres = pytest.mark.skipif(not POSTGRES_URL, reason="set ACEX_TEST_POSTGRES_URL to run against PostgreSQL")


def load_migration():
    spec = importlib.util.spec_from_file_location("timestamps_with_time_zone", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_migration()
BEFORE = MODULE.down_revision
AFTER = MODULE.revision


def alembic_config(engine) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.attributes["connection"] = engine
    return config


def repository(**times) -> GitRepositoryRow:
    return GitRepositoryRow(
        name=f"repo-{uuid.uuid4().hex[:8]}",
        url="https://git.example/configs.git",
        auth_method="https_anonymous",
        created_by="test",
        updated_by="test",
        **times,
    )


def stored(engine, column: str, repo_id: int) -> str:
    """What the column holds, as text and in the session's own zone."""
    with engine.connect() as connection:
        return connection.execute(
            text(f"select {column}::text from git_repository where id = :id"), {"id": repo_id}
        ).scalar()


def column_types(engine) -> set[str]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "select distinct data_type from information_schema.columns "
                "where table_schema = 'public' and data_type like 'timestamp%'"
            )
        )
        return {row[0] for row in rows}


def read(engine, repo_id: int) -> GitRepositoryRow:
    with Session(engine) as session:
        return session.get(GitRepositoryRow, repo_id)


#: Datetime columns that migrations after this one add. Their own migration creates them as
#: `sa.DateTime(timezone=True)`, never as a plain `sa.DateTime()`, which is what made this migration necessary.
LATER: set[tuple[str, str]] = set()


def should_list_every_datetime_column_of_the_models():
    """The migration converts every datetime column there was. A column the models gain later is listed in LATER above,
    which says that its own migration made it `timestamptz`."""
    from sqlalchemy import DateTime
    from sqlmodel import SQLModel

    in_models = {
        (table.name, column.name)
        for table in SQLModel.metadata.sorted_tables
        for column in table.columns
        if isinstance(getattr(column.type, "impl", column.type), DateTime)
    }
    assert in_models == set(MODULE._COLUMNS) | LATER


def should_name_only_listed_columns_as_written_in_utc_before():
    assert MODULE._LEGACY <= set(MODULE._COLUMNS)


def should_leave_sqlite_alone(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = DatabaseManager(Connection(backend="sqlite", dbname="migrating.db"))
    manager.upgrade(BEFORE)
    with Session(manager.connection.engine) as session:
        row = repository(last_checked_at=WINTER)
        session.add(row)
        session.commit()
        repo_id = row.id

    manager.upgrade(AFTER)

    assert read(manager.connection.engine, repo_id).last_checked_at == WINTER
    command.downgrade(alembic_config(manager.connection.engine), BEFORE)
    assert read(manager.connection.engine, repo_id).last_checked_at == WINTER


@pytest.fixture
def server_zone_amsterdam():
    """A fresh database on the test server, and engines that open their sessions in the given zone."""
    admin = create_engine(POSTGRES_URL, isolation_level="AUTOCOMMIT")
    name = f"acex_ts_{uuid.uuid4().hex[:10]}"
    with admin.connect() as connection:
        connection.execute(text(f'create database "{name}"'))
    url = make_url(POSTGRES_URL).set(database=name)
    engines = []

    def engine(zone: str = "Europe/Amsterdam"):
        created = create_engine(url, connect_args={"options": f"-c TimeZone={zone}"})
        engines.append(created)
        return created

    yield engine
    for created in engines:
        created.dispose()
    with admin.connect() as connection:
        connection.execute(text(f'drop database if exists "{name}" with (force)'))
    admin.dispose()


@needs_postgres
def should_keep_the_moment_old_rows_stood_for(server_zone_amsterdam):
    amsterdam = server_zone_amsterdam()
    command.upgrade(alembic_config(amsterdam), BEFORE)
    assert column_types(amsterdam) == {"timestamp without time zone"}

    # Written the way the backend writes: aware UTC through the models.
    with Session(amsterdam) as session:
        row = repository(last_checked_at=WINTER, last_synced_at=SUMMER)
        session.add(row)
        session.commit()
        repo_id = row.id
    # Before: the server's wall clock, one and two hours ahead of UTC.
    assert stored(amsterdam, "last_checked_at", repo_id) == "2026-11-25 14:13:54.427564"
    assert stored(amsterdam, "last_synced_at", repo_id) == "2026-07-01 12:00:00"

    command.upgrade(alembic_config(amsterdam), AFTER)

    assert column_types(amsterdam) == {"timestamp with time zone"}
    # After: the same instants, read back the same through the models.
    row = read(amsterdam, repo_id)
    assert row.last_checked_at == WINTER
    assert row.last_synced_at == SUMMER
    with amsterdam.connect() as connection:
        utc = connection.execute(
            text("select (last_checked_at at time zone 'UTC')::text from git_repository where id = :id"),
            {"id": repo_id},
        ).scalar()
    assert utc == "2026-11-25 13:13:54.427564"


@needs_postgres
def should_not_depend_on_the_zone_of_the_session_afterwards(server_zone_amsterdam):
    amsterdam = server_zone_amsterdam()
    command.upgrade(alembic_config(amsterdam), BEFORE)
    with Session(amsterdam) as session:
        row = repository(last_checked_at=WINTER)
        session.add(row)
        session.commit()
        repo_id = row.id
    command.upgrade(alembic_config(amsterdam), AFTER)

    for zone in ("UTC", "America/New_York", "Asia/Tokyo"):
        assert read(server_zone_amsterdam(zone), repo_id).last_checked_at == WINTER, zone

    # And a row written in any zone is the same instant for everyone.
    tokyo = server_zone_amsterdam("Asia/Tokyo")
    with Session(tokyo) as session:
        row = repository(last_checked_at=SUMMER)
        session.add(row)
        session.commit()
        written = row.id
    assert read(amsterdam, written).last_checked_at == SUMMER


@needs_postgres
def should_leave_no_timestamp_without_zone_and_be_repeatable(server_zone_amsterdam):
    amsterdam = server_zone_amsterdam()
    command.upgrade(alembic_config(amsterdam), "head")
    assert column_types(amsterdam) == {"timestamp with time zone"}

    # Running the body again changes nothing: the columns are done.
    with amsterdam.begin() as connection:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        with Operations.context(MigrationContext.configure(connection)):
            MODULE.upgrade()
    assert column_types(amsterdam) == {"timestamp with time zone"}


@needs_postgres
def should_go_back_to_the_wall_clock_on_downgrade(server_zone_amsterdam):
    amsterdam = server_zone_amsterdam()
    command.upgrade(alembic_config(amsterdam), BEFORE)
    with Session(amsterdam) as session:
        row = repository(last_checked_at=WINTER, last_synced_at=SUMMER)
        session.add(row)
        session.commit()
        repo_id = row.id
    command.upgrade(alembic_config(amsterdam), AFTER)

    command.downgrade(alembic_config(amsterdam), BEFORE)

    assert column_types(amsterdam) == {"timestamp without time zone"}
    assert stored(amsterdam, "last_checked_at", repo_id) == "2026-11-25 14:13:54.427564"
    assert stored(amsterdam, "last_synced_at", repo_id) == "2026-07-01 12:00:00"


def device_config_row(engine, created: str | None = None, written: datetime | None = None) -> int:
    """A device config stored the way the old code stored it (`created`, the UTC clock as text) or the way the
    current code stores it (`written`, an aware value through the models)."""
    if written is not None:
        with Session(engine) as session:
            row = StoredDeviceConfig(node_instance_id="n", content="c", hash="h", created_at=written)
            session.add(row)
            session.commit()
            return row.id
    with engine.begin() as connection:
        return connection.execute(
            text(
                "insert into device_config (node_instance_id, content, hash, created_at) "
                "values ('n', 'c', 'h', :created) returning id"
            ),
            {"created": created},
        ).scalar()


def moment(engine, table: str, column: str, row_id: int) -> str:
    """The moment a `timestamptz` column holds, as UTC clock text."""
    with engine.connect() as connection:
        return connection.execute(
            text(f"select ({column} at time zone 'UTC')::text from {table} where id = :id"), {"id": row_id}
        ).scalar()


def clock(engine, table: str, column: str, row_id: int) -> str:
    with engine.connect() as connection:
        return connection.execute(text(f"select {column}::text from {table} where id = :id"), {"id": row_id}).scalar()


@needs_postgres
def should_read_the_rows_the_old_code_wrote_as_the_utc_clock(server_zone_amsterdam):
    amsterdam = server_zone_amsterdam()
    command.upgrade(alembic_config(amsterdam), BEFORE)
    old = device_config_row(amsterdam, created="2026-09-03 14:21:34")  # written by utcnow(): the UTC clock
    last_old = device_config_row(amsterdam, created="2026-09-22 15:59:59")
    first_new = device_config_row(amsterdam, created="2026-09-22 16:00:00")  # a server clock, UTC+2 that day
    new = device_config_row(amsterdam, written=WINTER)  # written by now(UTC): the server clock, 14:13:54
    with Session(amsterdam) as session:  # a column that was never written as the UTC clock, early in September
        other = repository(created_at=datetime(2026, 9, 3, 12, 21, 34, tzinfo=UTC))
        session.add(other)
        session.commit()
        other_id = other.id
    assert clock(amsterdam, "device_config", "created_at", new) == "2026-11-25 14:13:54.427564"

    command.upgrade(alembic_config(amsterdam), AFTER)

    assert moment(amsterdam, "device_config", "created_at", old) == "2026-09-03 14:21:34"
    assert moment(amsterdam, "device_config", "created_at", last_old) == "2026-09-22 15:59:59"
    assert moment(amsterdam, "device_config", "created_at", first_new) == "2026-09-22 14:00:00"
    assert moment(amsterdam, "device_config", "created_at", new) == "2026-11-25 13:13:54.427564"
    assert moment(amsterdam, "git_repository", "created_at", other_id) == "2026-09-03 12:21:34"


@needs_postgres
def should_give_old_utc_rows_back_as_the_utc_clock_on_downgrade(server_zone_amsterdam):
    amsterdam = server_zone_amsterdam()
    command.upgrade(alembic_config(amsterdam), BEFORE)
    old = device_config_row(amsterdam, created="2026-09-03 14:21:34")
    new = device_config_row(amsterdam, written=WINTER)
    command.upgrade(alembic_config(amsterdam), AFTER)

    command.downgrade(alembic_config(amsterdam), BEFORE)

    assert clock(amsterdam, "device_config", "created_at", old) == "2026-09-03 14:21:34"
    assert clock(amsterdam, "device_config", "created_at", new) == "2026-11-25 14:13:54.427564"
