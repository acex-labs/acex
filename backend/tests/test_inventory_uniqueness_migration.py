"""The migration behind the unique indexes: they are only created when the data has no duplicates.

The migrations run when the backend starts, so one that finds duplicate rows must log them and leave the index
out rather than stop the backend from starting.
"""

import importlib.util
import logging
from pathlib import Path

import pytest
from acex.database import Connection, DatabaseManager
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

BEFORE = "f4b8d2a6c9e1"
REVISION = "c8d4f2a7e1b3"
INDEXES = {
    "uq_asset_serial_number_norm",
    "uq_logicalnode_hostname_norm",
    "uq_node_logical_node_id",
    "uq_node_asset_ref",
}
MIGRATIONS = Path(__file__).parent.parent / "src/acex/migrations"
MIGRATION = MIGRATIONS / "versions/c8d4f2a7e1b3_unique_inventory_identities.py"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = DatabaseManager(Connection(backend="sqlite", dbname="migrating.db"))
    manager.upgrade(BEFORE)
    return manager


def downgrade(db, revision):
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.attributes["connection"] = db.connection.engine
    command.downgrade(config, revision)


def execute(db, statement, **params):
    with db.connection.engine.begin() as connection:
        return connection.execute(text(statement), params)


def indexes(db) -> set[str]:
    with db.connection.engine.connect() as connection:
        names = connection.execute(text("SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'uq_%'"))
        return {name for (name,) in names}


def add_asset(db, serial):
    execute(
        db,
        "INSERT INTO asset (vendor, serial_number, os, os_version, hardware_model)"
        " VALUES ('cisco', :serial, 'cisco_iosxe', '17.9', 'C9300')",
        serial=serial,
    )


def add_logical_node(db, hostname):
    execute(db, "INSERT INTO logicalnode (hostname, role) VALUES (:hostname, 'core')", hostname=hostname)


def add_node(db, asset_id, logical_node_id, ref_type="asset"):
    execute(
        db,
        "INSERT INTO node (asset_ref_id, asset_ref_type, logical_node_id, created_at, admin_status, provision_status)"
        " VALUES (:asset, :ref_type, :logical, '2026-01-01 00:00:00', 'planned', 'unprovisioned')",
        asset=asset_id,
        ref_type=ref_type,
        logical=logical_node_id,
    )


def version(db) -> str:
    return execute(db, "SELECT version_num FROM alembic_version").scalar()


def warnings(caplog) -> str:
    return "\n".join(r.getMessage() for r in caplog.records if r.name == "acex.migrations")


def load_migration():
    """The migration module on its own, to run its steps without Alembic's loader."""
    spec = importlib.util.spec_from_file_location("unique_inventory_identities", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestUpgrade:
    def should_add_the_indexes_when_there_are_no_duplicates(self, db):
        add_asset(db, "A1")
        add_asset(db, "A1-2")
        add_logical_node(db, "sw-01")
        add_logical_node(db, "sw-02")
        add_node(db, 1, 1)
        add_node(db, 2, 2)

        db.upgrade("head")

        assert indexes(db) == INDEXES
        assert version(db) == REVISION

    def should_treat_an_asset_and_a_cluster_with_the_same_id_as_different(self, db):
        add_logical_node(db, "sw-01")
        add_logical_node(db, "sw-02")
        add_node(db, 1, 1)
        add_node(db, 1, 2, ref_type="asset_cluster")

        db.upgrade("head")

        assert "uq_node_asset_ref" in indexes(db)

    def should_leave_an_index_out_and_say_which_rows_when_there_are_duplicates(self, db, caplog):
        add_asset(db, "x1")
        add_asset(db, "other")
        add_asset(db, "X1 ")
        add_logical_node(db, "sw-01")
        add_node(db, 1, 1)

        with caplog.at_level(logging.WARNING, logger="acex.migrations"):
            db.upgrade("head")

        assert indexes(db) == INDEXES - {"uq_asset_serial_number_norm"}  # the others are clean
        assert version(db) == REVISION  # the backend starts
        message = warnings(caplog)
        assert "uq_asset_serial_number_norm was not created" in message
        assert "x1: id 1 ('x1'), id 3 ('X1 ')" in message
        assert "CREATE UNIQUE INDEX uq_asset_serial_number_norm ON asset (lower(trim(serial_number)));" in message

    def should_leave_out_each_index_that_has_duplicates(self, db, caplog):
        add_asset(db, "A1")
        add_logical_node(db, "sw-01")
        add_logical_node(db, "SW-01")
        add_node(db, 1, 1)
        add_node(db, 1, 1)

        with caplog.at_level(logging.WARNING, logger="acex.migrations"):
            db.upgrade("head")

        assert indexes(db) == {"uq_asset_serial_number_norm"}
        message = warnings(caplog)
        assert "uq_logicalnode_hostname_norm was not created" in message
        assert "uq_node_logical_node_id was not created" in message
        assert "uq_node_asset_ref was not created" in message
        assert "sw-01: id 1 ('sw-01'), id 2 ('SW-01')" in message
        assert "CREATE UNIQUE INDEX uq_node_logical_node_id ON node (logical_node_id);" in message

    def should_name_the_node_instances_that_share_an_asset(self, db, caplog):
        add_logical_node(db, "sw-01")
        add_logical_node(db, "sw-02")
        add_node(db, 1, 1)
        add_node(db, 1, 2)

        with caplog.at_level(logging.WARNING, logger="acex.migrations"):
            db.upgrade("head")

        assert indexes(db) == INDEXES - {"uq_node_asset_ref"}
        message = warnings(caplog)
        assert "asset 1: id 1, id 2" in message
        assert "CREATE UNIQUE INDEX uq_node_asset_ref ON node (asset_ref_type, asset_ref_id);" in message

    def should_list_only_so_many_duplicates(self, db, caplog):
        for i in range(55):
            add_asset(db, f"S{i}")
            add_asset(db, f"s{i}")

        with caplog.at_level(logging.WARNING, logger="acex.migrations"):
            db.upgrade("head")

        message = warnings(caplog)
        assert "55 duplicate group(s)" in message
        assert "... and 5 more" in message

    def should_not_stop_when_a_duplicate_arrives_while_the_index_is_built(self, db, caplog):
        # The check found none, then another row was written before the index was created.
        add_asset(db, "x1")
        add_asset(db, "X1")
        migration = load_migration()
        migration._duplicates = lambda *args: []

        with caplog.at_level(logging.WARNING, logger="acex.migrations"):
            with db.connection.engine.begin() as connection:
                with Operations.context(MigrationContext.configure(connection)):
                    migration.upgrade()

        assert indexes(db) == INDEXES - {"uq_asset_serial_number_norm"}
        assert "uq_asset_serial_number_norm was not created: the table changed" in warnings(caplog)


class TestDowngrade:
    def should_drop_the_indexes(self, db):
        db.upgrade("head")
        assert indexes(db) == INDEXES

        downgrade(db, BEFORE)

        assert indexes(db) == set()
        assert version(db) == BEFORE

    def should_not_mind_an_index_that_was_never_created(self, db):
        add_asset(db, "x1")
        add_asset(db, "X1")
        db.upgrade("head")
        assert "uq_asset_serial_number_norm" not in indexes(db)

        downgrade(db, BEFORE)

        assert indexes(db) == set()
