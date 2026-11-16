"""Global search over the inventory, against a real SQLite database."""

import asyncio

import pytest
from acex.database import Connection, DatabaseManager
from acex.models import Asset, AssetCluster, Contact, LogicalNode, ManagementConnection, Node, Region, Site
from acex.search import SearchService
from sqlmodel import Session


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = DatabaseManager(Connection(backend="sqlite", dbname="search.db"))
    manager.create_tables()
    with Session(manager.connection.engine) as session:
        session.add_all(
            [
                Site(name="sto1", display_name="Stockholm DC", city="Stockholm", country="SE"),
                Site(name="got1", display_name="Göteborg", city="Gothenburg", country="SE"),
                Region(name="nordics", display_name="Nordics"),
                Contact(name="noc", display_name="Network Operations", email="noc@example.com"),
                AssetCluster(name="sto1-stack"),
            ]
        )
        for hostname, site, serial, ip in [
            ("sto1-core-01", "sto1", "FOC111", "10.0.0.1"),
            ("sto1-access-01", "sto1", "FOC222", "10.0.0.2"),
            ("got1-core-01", "got1", "FOC333", "10.1.0.1"),
            ("sto", "lab", "FOC_44", "192.168.0.4"),
        ]:
            logical_node = LogicalNode(hostname=hostname, role="core", site=site, sequence=1)
            asset = Asset(vendor="cisco", hardware_model="C9300", serial_number=serial, os="cisco_iosxe")
            session.add_all([logical_node, asset])
            session.flush()
            node = Node(asset_ref_id=asset.id, logical_node_id=logical_node.id)
            session.add(node)
            session.flush()
            session.add(ManagementConnection(node_id=node.id, target_ip=ip, primary=True))
        session.add(LogicalNode(hostname="sto1-spare-01", role="access", site="sto1", sequence=2))
        session.commit()
    return manager


def search(db, q, limit=5):
    return asyncio.run(SearchService(db).search(q, limit=limit))


def groups(response):
    return {g.type.value: g for g in response.groups}


def test_short_query_returns_nothing(db):
    assert search(db, " s ").groups == []


def test_matches_every_kind_and_skips_empty_groups(db):
    found = groups(search(db, "sto"))
    assert set(found) == {"logical_node", "node_instance", "site", "asset_cluster"}
    assert found["logical_node"].total == 4
    assert found["node_instance"].total == 3
    assert found["site"].items[0].label == "sto1"


def test_exact_match_ranks_first_then_prefix(db):
    hits = groups(search(db, "sto"))["logical_node"].items
    assert [h.label for h in hits] == ["sto", "sto1-access-01", "sto1-core-01", "sto1-spare-01"]


def test_hit_in_first_field_outranks_hit_in_later_field(db):
    with Session(db.connection.engine) as session:
        session.add(LogicalNode(hostname="lab-1", role="core", site="sto1", sequence=3))
        session.commit()
    hits = groups(search(db, "sto1"))["logical_node"].items
    assert hits[-1].label == "lab-1"
    assert hits[-1].matched_field == "site"


def test_limit_caps_items_but_not_total(db):
    group = groups(search(db, "sto1", limit=2))["logical_node"]
    assert group.total == 3
    assert len(group.items) == 2


def test_case_insensitive(db):
    assert groups(search(db, "STOCKHOLM"))["site"].items[0].matched_field == "display_name"


def test_node_instance_by_management_ip(db):
    hit = groups(search(db, "10.1.0"))["node_instance"].items[0]
    assert (hit.label, hit.matched_field, hit.matched_value) == ("got1-core-01", "management_ip", "10.1.0.1")
    assert hit.sublabel == "got1 · FOC333"


def test_node_instance_and_asset_by_serial(db):
    found = groups(search(db, "foc222"))
    assert found["node_instance"].items[0].label == "sto1-access-01"
    assert found["asset"].items[0].sublabel == "cisco · C9300"


def test_wildcards_in_query_are_literal(db):
    assert [h.label for h in groups(search(db, "C_44"))["asset"].items] == ["FOC_44"]
    assert search(db, "%%").groups == []


def test_contact_by_email(db):
    hit = groups(search(db, "example.com"))["contact"].items[0]
    assert (hit.label, hit.matched_field) == ("Network Operations", "email")


def test_region(db):
    assert groups(search(db, "nordic"))["region"].items[0].label == "nordics"
