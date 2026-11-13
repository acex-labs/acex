"""``q`` on the asset list: one search text across the fields that identify an asset."""

import asyncio
from types import SimpleNamespace

import pytest
from acex.database import Connection, DatabaseManager
from acex.inventory.asset_service import AssetService
from acex.models import Asset, Node
from acex.models.logical_node import LogicalNode
from acex.plugins.adaptors.asset_adapter import AssetAdapter
from acex.plugins.integrations.database import DatabasePlugin
from sqlmodel import Session

CISCO_SERIAL = "FOC1111A1B2"
JUNIPER_SERIAL = "JN2222X9Y8"
ARISTA_SERIAL = "AR3333Q7W6"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = DatabaseManager(Connection(backend="sqlite", dbname="assets.db"))
    manager.create_tables()
    return manager


@pytest.fixture
def service(db):
    # ``query`` never touches the hardware model registry.
    return AssetService(AssetAdapter(DatabasePlugin(db, Asset)), hardware_models=SimpleNamespace())


def add_asset(db, serial, vendor="cisco", model="C9300", os="cisco_iosxe", ned_id=None) -> int:
    with Session(db.connection.engine) as session:
        asset = Asset(vendor=vendor, serial_number=serial, hardware_model=model, os=os, ned_id=ned_id)
        session.add(asset)
        session.commit()
        return asset.id


def assign(db, asset_id):
    """Give the asset a node, which is what makes it assigned."""
    with Session(db.connection.engine) as session:
        logical_node = LogicalNode(hostname=f"node-{asset_id}", role="core", site="lab", sequence=1)
        session.add(logical_node)
        session.flush()
        session.add(Node(asset_ref_id=asset_id, logical_node_id=logical_node.id))
        session.commit()


@pytest.fixture
def assets(db):
    """Three assets that differ in every searched field. Ids in insertion order."""
    return SimpleNamespace(
        cisco=add_asset(db, CISCO_SERIAL, "cisco", "C9300-48P", "cisco_iosxe", "CiscoIOSCLIDriver"),
        juniper=add_asset(db, JUNIPER_SERIAL, "juniper", "EX4300", "juniper_junos", "JuniperJunosCLIDriver"),
        arista=add_asset(db, ARISTA_SERIAL, "arista", "DCS-7050", "arista_eos"),
    )


def search(service, **kwargs):
    # Sorted by serial so the order never depends on the database.
    return asyncio.run(service.query(sort="serial_number", **kwargs))


def serials(service, **kwargs):
    return [asset.serial_number for asset in search(service, **kwargs).items]


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        pytest.param("JN2222", [JUNIPER_SERIAL], id="serial number"),
        pytest.param("c9300", [CISCO_SERIAL], id="hardware model"),
        pytest.param("arista", [ARISTA_SERIAL], id="vendor (arista has no ned id, so only vendor matches)"),
        pytest.param("junosclidriver", [JUNIPER_SERIAL], id="ned id (no other field contains it)"),
    ],
)
def test_q_matches_each_searched_field(service, assets, q, expected):
    assert serials(service, q=q) == expected


def test_q_matches_as_a_contains_not_a_prefix(service, assets):
    assert serials(service, q="2222X9") == [JUNIPER_SERIAL]


def test_q_ignores_case_in_either_direction(service, assets):
    assert serials(service, q="foc1111a1b2") == [CISCO_SERIAL]
    assert serials(service, q="Foc1111a1B2") == [CISCO_SERIAL]
    assert serials(service, q="CISCO") == [CISCO_SERIAL]


def test_q_is_trimmed(service, assets):
    assert serials(service, q="  c9300 ") == [CISCO_SERIAL]


def test_a_search_with_no_match_is_empty_and_counts_zero(service, assets):
    result = search(service, q="no-such-asset")

    assert result.items == []
    assert result.total == 0


@pytest.mark.parametrize("q", [None, "", "   "])
def test_a_blank_q_does_not_filter(service, assets, q):
    assert serials(service, q=q) == [ARISTA_SERIAL, CISCO_SERIAL, JUNIPER_SERIAL]


def test_wildcard_characters_are_matched_literally(db, service):
    add_asset(db, "A_1")
    add_asset(db, "AB1")
    add_asset(db, "50%OFF")

    assert serials(service, q="A_1") == ["A_1"]  # "_" is not "any one character"
    assert serials(service, q="%") == ["50%OFF"]  # "%" is not "anything"


def test_q_narrows_together_with_the_other_filters(service, assets):
    # "9" is in the cisco model (C9300-48P) and the juniper serial (JN2222X9Y8).
    assert serials(service, q="9") == [CISCO_SERIAL, JUNIPER_SERIAL]
    assert serials(service, q="9", vendor="juniper") == [JUNIPER_SERIAL]
    assert serials(service, q="9", vendor="arista") == []


def test_q_narrows_together_with_assigned(db, service, assets):
    assign(db, assets.cisco)

    assert serials(service, q="9", assigned=False) == [JUNIPER_SERIAL]
    assert serials(service, q="9", assigned=True) == [CISCO_SERIAL]


def test_total_counts_every_match_not_just_the_page(service, assets):
    first = search(service, q="9", limit=1)
    second = search(service, q="9", limit=1, offset=1)

    assert first.total == second.total == 2
    assert [a.serial_number for a in first.items] == [CISCO_SERIAL]
    assert [a.serial_number for a in second.items] == [JUNIPER_SERIAL]
