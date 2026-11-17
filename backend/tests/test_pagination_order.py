"""A list asked for without a sort still comes back in a fixed order, so paging through it is complete."""

import re

import pytest
from acex.database import Connection, DatabaseManager
from acex.models import Asset
from acex.models.logical_node import LogicalNode
from acex.models.sites import Site
from acex.plugins.integrations.database import DatabasePlugin
from sqlalchemy import event
from sqlmodel import Session

# model and a row factory
LISTS = {
    "site": (Site, lambda i: Site(name=f"site-{i:02d}")),
    "logical_node": (
        LogicalNode,
        lambda i: LogicalNode(hostname=f"host-{i:02d}", role="core", site="lab", sequence=i),
    ),
    "asset": (
        Asset,
        lambda i: Asset(vendor="cisco", serial_number=f"SN-{i:02d}", os="cisco_iosxe", hardware_model="C9300"),
    ),
}


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = DatabaseManager(Connection(backend="sqlite", dbname="pagination.db"))
    manager.create_tables()
    return manager


@pytest.fixture(params=LISTS)
def listing(request, db):
    model, make = LISTS[request.param]
    with Session(db.connection.engine) as session:
        session.add_all([make(i) for i in range(5)])
        session.commit()
    return db, DatabasePlugin(db, model), model.__table__.name


def page_sql(db, plugin):
    """The SELECT that fetches the page (the one with a LIMIT), as the database receives it.

    SQLite hands rows back in insertion order whatever the query says, so walking the pages
    cannot show that an ORDER BY is missing. PostgreSQL gives no such order.
    """
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db.connection.engine, "before_cursor_execute", capture)
    try:
        plugin.query(limit=2, offset=0)
    finally:
        event.remove(db.connection.engine, "before_cursor_execute", capture)
    page = [s for s in statements if "LIMIT" in s]
    assert len(page) == 1, statements
    return page[0]


def test_a_list_without_a_sort_is_ordered_by_id(listing):
    db, plugin, table = listing
    order_by = re.search(r"ORDER BY (.+?)\s+LIMIT", page_sql(db, plugin), re.S).group(1)
    assert " ".join(order_by.split()) == f"{table}.id"
