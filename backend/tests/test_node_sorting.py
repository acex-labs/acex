import asyncio
import ipaddress
from types import SimpleNamespace

import pytest
from acex.database import Connection, DatabaseManager
from acex.inventory.node_service import NodeService
from acex.models import Asset, ManagementConnection, Node
from acex.models.logical_node import LogicalNode
from acex.plugins.adaptors.node_adapter import NodeAdapter
from acex.plugins.integrations.database import DatabasePlugin
from fastapi import HTTPException
from sqlmodel import Session

CISCO = "CiscoIOSCLIDriver"
JUNIPER = "JuniperJunosCLIDriver"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = DatabaseManager(Connection(backend="sqlite", dbname="nodes.db"))
    manager.create_tables()
    return manager


@pytest.fixture
def service(db):
    def get_asset(asset_id):
        with Session(db.connection.engine) as session:
            return session.get(Asset, asset_id)

    inventory = SimpleNamespace(assets=SimpleNamespace(adapter=SimpleNamespace(get=get_asset)))
    return NodeService(NodeAdapter(DatabasePlugin(db, Node)), inventory)


def add_node(db, hostname, connections=(), ned_id=CISCO):
    with Session(db.connection.engine) as session:
        logical_node = LogicalNode(hostname=hostname, role="core", site="lab", sequence=1)
        asset = Asset(
            vendor="cisco",
            hardware_model="C9300",
            serial_number=f"SN-{hostname}",
            os="cisco_iosxe",
            os_version="17.9",
            ned_id=ned_id,
        )
        session.add_all([logical_node, asset])
        session.flush()
        node = Node(asset_ref_id=asset.id, logical_node_id=logical_node.id)
        session.add(node)
        session.flush()
        for target_ip, primary in connections:
            session.add(ManagementConnection(node_id=node.id, target_ip=target_ip, primary=primary))
        session.commit()


def hostnames(service, **kwargs):
    return [node.hostname for node in asyncio.run(service.query(**kwargs)).items]


def test_ip_addresses_sort_numerically(db, service):
    ips = ["10.0.0.10", "10.0.0.9", "192.168.1.20", "0.0.0.0", "255.255.255.255", "9.255.255.255", "10.0.0.2"]
    for ip in ips:
        add_node(db, ip, [(ip, True)])
    expected = sorted(ips, key=ipaddress.IPv4Address)

    assert hostnames(service, sort="ip", order="asc") == expected
    assert hostnames(service, sort="ip", order="desc") == expected[::-1]


def test_the_primary_connection_decides_where_a_node_sorts(db, service):
    add_node(db, "late", [("10.0.0.1", False), ("192.168.1.20", True)])
    add_node(db, "early", [("10.0.0.2", True)])

    assert hostnames(service, sort="ip") == ["early", "late"]


@pytest.mark.parametrize("order", ["asc", "desc"])
def test_nodes_without_a_usable_address_sort_together(db, service, order):
    add_node(db, "10.0.0.5", [("10.0.0.5", True)])
    add_node(db, "10.0.0.7", [("10.0.0.7", True)])
    unusable = {"name": "core.example.net", "range": "10.0.0.256", "zero": "01.2.3.4", "blank": ""}
    for hostname, target_ip in unusable.items():
        add_node(db, hostname, [(target_ip, True)])
    add_node(db, "none")

    names = hostnames(service, sort="ip", order=order)

    assert [n for n in names if n[0].isdigit()] == (
        ["10.0.0.5", "10.0.0.7"] if order == "asc" else ["10.0.0.7", "10.0.0.5"]
    )
    positions = [i for i, n in enumerate(names) if not n[0].isdigit()]
    assert positions in (list(range(5)), list(range(2, 7)))


@pytest.mark.parametrize("order", ["asc", "desc"])
@pytest.mark.parametrize("column", sorted(NodeService.SORTABLE_COLUMNS))
def test_every_sortable_column_can_be_used(db, service, column, order):
    add_node(db, "a", [("10.0.0.1", True)], ned_id=CISCO)
    add_node(db, "b", [("10.0.0.2", True)], ned_id=JUNIPER)

    assert sorted(hostnames(service, sort=column, order=order)) == ["a", "b"]


def test_drivers_sort_by_their_ned(db, service):
    add_node(db, "juniper", ned_id=JUNIPER)
    add_node(db, "cisco", ned_id=CISCO)

    assert hostnames(service, sort="ned_id") == ["cisco", "juniper"]
    assert hostnames(service, sort="ned_id", order="desc") == ["juniper", "cisco"]


def test_an_unknown_sort_column_is_a_400(service):
    with pytest.raises(HTTPException) as error:
        asyncio.run(service.query(sort="bogus"))

    assert error.value.status_code == 400
    assert "'bogus'" in error.value.detail


def test_a_node_read_on_its_own_carries_its_management_connections(db):
    # Drivers open a session at a node's management connection, so a single read must hold them,
    # primary first as in a listing.
    add_node(db, "lab-1", connections=[("10.0.0.2", False), ("10.0.0.1", True)])

    async def get_asset(asset_id):
        with Session(db.connection.engine) as session:
            asset = session.get(Asset, asset_id)
            asset.os_version = None  # the shared fixture's "17.9" is no full IOS-XE version
            return asset

    async def get_logical_node(logical_node_id):
        with Session(db.connection.engine) as session:
            logical_node = session.get(LogicalNode, logical_node_id)
            return SimpleNamespace(model_dump=logical_node.model_dump, regions=[])

    inventory = SimpleNamespace(
        assets=SimpleNamespace(get=get_asset),
        logical_nodes=SimpleNamespace(get=get_logical_node),
        credential_manager=None,
    )
    node = asyncio.run(NodeService(NodeAdapter(DatabasePlugin(db, Node)), inventory).get("1"))

    assert [(c.target_ip, c.primary) for c in node.management_connections] == [("10.0.0.1", True), ("10.0.0.2", False)]
