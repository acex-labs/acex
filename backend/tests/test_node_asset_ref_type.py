"""A node is bound to an asset or to an asset cluster, and ``asset_ref_id`` alone cannot tell which: an asset and a
cluster can have the same id. ``asset_ref_type`` on the node list narrows the answer to one of them."""

import asyncio
from types import SimpleNamespace

import pytest
from acex.api.routers import node_instances
from acex.database import Connection, DatabaseManager
from acex.inventory.node_service import NodeService
from acex.models import Asset, AssetCluster, Node
from acex.models.asset import AssetClusterLink
from acex.models.logical_node import LogicalNode
from acex.plugins.adaptors.node_adapter import NodeAdapter
from acex.plugins.integrations.database import DatabasePlugin
from acex_devkit.models.node_response import AssetRefType
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

NODES = "/api/v1/inventory/node_instances"


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

    def get_cluster(cluster_id):
        with Session(db.connection.engine) as session:
            return session.get(AssetCluster, cluster_id)

    inventory = SimpleNamespace(
        assets=SimpleNamespace(adapter=SimpleNamespace(get=get_asset)),
        asset_cluster_manager=SimpleNamespace(get_cluster=get_cluster),
    )
    return NodeService(NodeAdapter(DatabasePlugin(db, Node)), inventory)


def add_asset(db, serial) -> int:
    with Session(db.connection.engine) as session:
        asset = Asset(vendor="cisco", hardware_model="C9300", serial_number=serial, os="cisco_iosxe", os_version="17.9")
        session.add(asset)
        session.commit()
        return asset.id


def add_cluster(db, name, asset_ids) -> int:
    with Session(db.connection.engine) as session:
        cluster = AssetCluster(name=name)
        session.add(cluster)
        session.flush()
        for order, asset_id in enumerate(asset_ids):
            session.add(AssetClusterLink(asset_id=asset_id, cluster_id=cluster.id, order=order))
        session.commit()
        return cluster.id


def add_node(db, hostname, ref_id, ref_type) -> int:
    with Session(db.connection.engine) as session:
        logical_node = LogicalNode(hostname=hostname, role="core", site="lab", sequence=1)
        session.add(logical_node)
        session.flush()
        node = Node(asset_ref_id=ref_id, asset_ref_type=ref_type, logical_node_id=logical_node.id)
        session.add(node)
        session.commit()
        return node.id


@pytest.fixture
def same_id(db):
    """Standalone asset 1 and cluster 1, which holds assets 2 and 3. Only the cluster has a node."""
    standalone, member_a, member_b = (add_asset(db, f"SN-{n}") for n in range(3))
    cluster = add_cluster(db, "stack-1", [member_a, member_b])
    assert standalone == cluster
    return SimpleNamespace(
        id=standalone, cluster_node=add_node(db, "stack-1-node", cluster, AssetRefType.asset_cluster)
    )


def hostnames(service, **kwargs):
    return [node.hostname for node in asyncio.run(service.query(**kwargs)).items]


class TestAnAssetAndAClusterWithTheSameId:
    def should_not_show_the_cluster_node_as_bound_to_the_asset(self, service, same_id):
        assert hostnames(service, asset_ref_id=same_id.id, asset_ref_type=AssetRefType.asset) == []

    def should_find_the_cluster_node_by_the_cluster_type(self, service, same_id):
        assert hostnames(service, asset_ref_id=same_id.id, asset_ref_type=AssetRefType.asset_cluster) == [
            "stack-1-node"
        ]

    def should_find_the_node_bound_to_the_asset_even_when_the_cluster_node_comes_first(self, db, service, same_id):
        add_node(db, "asset-node", same_id.id, AssetRefType.asset)

        page = asyncio.run(service.query(asset_ref_id=same_id.id, asset_ref_type=AssetRefType.asset, limit=1))

        assert [node.hostname for node in page.items] == ["asset-node"]
        assert page.total == 1

    def should_keep_answering_both_when_no_type_is_given(self, db, service, same_id):
        add_node(db, "asset-node", same_id.id, AssetRefType.asset)

        assert sorted(hostnames(service, asset_ref_id=same_id.id)) == ["asset-node", "stack-1-node"]


class TestTheNodeListOverHttp:
    @pytest.fixture
    def client(self, db, service):
        engine = SimpleNamespace(
            inventory=SimpleNamespace(node_instances=service),
            device_config_manager=SimpleNamespace(),
        )
        app = FastAPI()
        app.include_router(node_instances.create_router(engine))
        return TestClient(app)

    def should_take_the_type_as_a_query_parameter(self, client, same_id):
        as_asset = client.get(NODES, params={"asset_ref_id": same_id.id, "asset_ref_type": "asset"})
        as_cluster = client.get(NODES, params={"asset_ref_id": same_id.id, "asset_ref_type": "asset_cluster"})

        assert as_asset.status_code == 200
        assert as_asset.json()["items"] == []
        assert [node["hostname"] for node in as_cluster.json()["items"]] == ["stack-1-node"]

    def should_refuse_a_type_that_does_not_exist(self, client, same_id):
        response = client.get(NODES, params={"asset_ref_id": same_id.id, "asset_ref_type": "cluster"})

        assert response.status_code == 422
