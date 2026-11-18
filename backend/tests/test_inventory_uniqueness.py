"""One asset per serial number, one logical node per hostname, one node instance per logical node.

The services refuse a duplicate with a 409 that names the record in the way; the unique indexes on the
models are what holds when two requests race. Serial numbers and hostnames are compared without
surrounding whitespace and ignoring case.
"""

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from acex.database import Connection, DatabaseManager
from acex.inventory import uniqueness
from acex.inventory.asset_cluster_manager import AssetClusterManager
from acex.inventory.asset_service import AssetService
from acex.inventory.logical_node_service import LogicalNodeService
from acex.inventory.node_service import NodeService
from acex.inventory.uniqueness import DuplicateError
from acex.models import Asset, LogicalNode, Node
from acex.plugins.adaptors.asset_adapter import AssetAdapter
from acex.plugins.adaptors.logical_node_adapter import LogicalNodeAdapter
from acex.plugins.adaptors.node_adapter import NodeAdapter
from acex.plugins.integrations.database import DatabasePlugin
from acex_devkit.models.asset import AssetClusterCreate, AssetUpdate
from acex_devkit.models.node_response import AssetRefType
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select


def run(coroutine):
    return asyncio.run(coroutine)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = DatabaseManager(Connection(backend="sqlite", dbname="inventory.db"))
    manager.create_tables()
    return manager


class Telemetry:
    """Stands in for the telemetry agent manager: records the node instances whose revisions were bumped."""

    def __init__(self):
        self.bumped = []

    @contextmanager
    def bumping_revisions_for_nodes(self, node_ids):
        yield
        self.bumped.append(list(node_ids))

    def bump_revisions_for_node(self, node_id):
        self.bumped.append([node_id])


@pytest.fixture
def telemetry():
    return Telemetry()


@pytest.fixture
def assets(db):
    return AssetService(
        AssetAdapter(DatabasePlugin(db, Asset)), hardware_models=SimpleNamespace(enable_for_asset=lambda *a, **k: None)
    )


@pytest.fixture
def logical_nodes(db, telemetry):
    return LogicalNodeService(
        LogicalNodeAdapter(DatabasePlugin(db, LogicalNode)),
        config_compiler=None,
        integrations=None,
        db_manager=db,
        telemetry_agent_manager=telemetry,
    )


@pytest.fixture
def clusters(db):
    return AssetClusterManager(db)


@pytest.fixture
def nodes(db, assets, logical_nodes, clusters, telemetry):
    inventory = SimpleNamespace(
        assets=assets, logical_nodes=logical_nodes, asset_cluster_manager=clusters, telemetry_agent_manager=telemetry
    )
    service = NodeService(NodeAdapter(DatabasePlugin(db, Node)), inventory)

    async def enriched(node):
        return node

    service._enrich_data = enriched  # what a node looks like once enriched is not under test
    return service


def new_asset(serial="ABC123", **fields):
    return Asset(**{"vendor": "cisco", "hardware_model": "C9300", "os": "cisco_iosxe"} | fields, serial_number=serial)


def new_logical_node(hostname="sw-01", **fields):
    return LogicalNode(**{"role": "core", "site": "lab"} | fields, hostname=hostname)


def refused(coroutine) -> DuplicateError:
    with pytest.raises(DuplicateError) as raised:
        run(coroutine)
    return raised.value


def move_to(logical_node_id):
    """The body of a PATCH that carries only the logical node, built the way FastAPI builds it."""
    return TypeAdapter(Node).validate_python({"logical_node_id": logical_node_id})


def move_to_asset(asset_id, asset_type="asset"):
    """The body of a PATCH that carries only the asset or cluster, as Change Asset sends it."""
    return TypeAdapter(Node).validate_python({"asset_ref_id": asset_id, "asset_ref_type": asset_type})


def rows(db, table):
    with Session(db.connection.engine) as session:
        return list(session.exec(select(table)))


class CountingAdapter:
    """Wraps an adapter and counts the lookups made through ``query``."""

    def __init__(self, adapter):
        self._adapter = adapter
        self.lookups = 0

    @property
    def plugin(self):
        return self._adapter.plugin

    def query(self, *args, **kwargs):
        self.lookups += 1
        return self._adapter.query(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._adapter, name)


class TestAssets:
    def should_refuse_a_serial_that_exists(self, assets):
        first = run(assets.create(new_asset("ABC123")))

        error = refused(assets.create(new_asset("ABC123")))

        assert error.status_code == 409
        assert error.detail == {
            "code": "duplicate",
            "message": f"Asset with serial number 'ABC123' already exists (id {first.id}).",
            "resource": "asset",
            "field": "serial_number",
            "value": "ABC123",
            "existing_id": first.id,
        }

    @pytest.mark.parametrize("serial", ["abc123", "  ABC123 ", "Abc123\t"])
    def should_ignore_case_and_padding(self, assets, db, serial):
        run(assets.create(new_asset("ABC123")))

        refused(assets.create(new_asset(serial)))

        assert len(rows(db, Asset)) == 1

    def should_store_the_serial_without_padding(self, assets, db):
        run(assets.create(new_asset("  abc123 ")))

        assert [a.serial_number for a in rows(db, Asset)] == ["abc123"]

    def should_not_take_a_longer_serial_for_a_duplicate(self, assets):
        run(assets.create(new_asset("ABC")))
        run(assets.create(new_asset("ABC-9")))

    @pytest.mark.parametrize("serial", ["", "   ", None])
    def should_refuse_a_blank_serial(self, assets, serial):
        with pytest.raises(HTTPException) as raised:
            run(assets.create(new_asset(serial)))

        assert raised.value.status_code == 422
        assert raised.value.detail[0]["loc"] == ["body", "serial_number"]

    def should_refuse_to_give_an_asset_the_serial_of_another(self, assets):
        run(assets.create(new_asset("A1")))
        other = run(assets.create(new_asset("B2")))

        error = refused(assets.update(str(other.id), AssetUpdate(serial_number="a1")))

        assert error.detail["field"] == "serial_number"

    def should_let_an_asset_keep_its_serial_and_change_its_case(self, assets, db):
        asset = run(assets.create(new_asset("abc123")))

        run(assets.update(str(asset.id), AssetUpdate(serial_number="abc123")))
        run(assets.update(str(asset.id), AssetUpdate(serial_number=" ABC123 ")))

        assert [a.serial_number for a in rows(db, Asset)] == ["ABC123"]

    def should_refuse_to_blank_a_serial(self, assets):
        asset = run(assets.create(new_asset()))

        for serial in (None, "  "):
            with pytest.raises(HTTPException) as raised:
                run(assets.update(str(asset.id), AssetUpdate(serial_number=serial)))
            assert raised.value.status_code == 422

    def should_not_look_for_a_duplicate_when_the_serial_is_left_alone(self, assets):
        asset = run(assets.create(new_asset("ABC123")))
        counted = CountingAdapter(assets.adapter)
        assets.adapter = counted

        run(assets.update(str(asset.id), AssetUpdate(hardware_model="C9300-48P")))
        run(assets.update(str(asset.id), AssetUpdate(serial_number="abc123")))  # only the case

        assert counted.lookups == 0

    def should_let_an_asset_that_already_has_a_duplicate_be_edited(self, assets, db):
        # What the migration leaves when it found duplicates: no unique index.
        with db.connection.engine.begin() as connection:
            connection.execute(text("DROP INDEX uq_asset_serial_number_norm"))
        first = run(assets.create(new_asset("ABC123")))
        with Session(db.connection.engine) as session:
            session.add(new_asset("ABC123"))
            session.commit()

        run(assets.update(str(first.id), AssetUpdate(hardware_model="C9300-48P", serial_number="ABC123")))

        assert {a.hardware_model for a in rows(db, Asset)} == {"C9300", "C9300-48P"}

    def should_answer_404_for_an_asset_that_is_not_there(self, assets):
        with pytest.raises(HTTPException) as raised:
            run(assets.update("999", AssetUpdate(serial_number="ABC123")))

        assert raised.value.status_code == 404


class TestLogicalNodes:
    def should_refuse_a_hostname_that_exists(self, logical_nodes):
        first = run(logical_nodes.create(new_logical_node("sw-01")))

        error = refused(logical_nodes.create(new_logical_node("SW-01 ", site="elsewhere")))

        assert error.detail["resource"] == "logical_node"
        assert error.detail["field"] == "hostname"
        assert error.detail["existing_id"] == first.id

    def should_refuse_a_blank_hostname(self, logical_nodes):
        with pytest.raises(HTTPException) as raised:
            run(logical_nodes.create(new_logical_node("  ")))

        assert raised.value.status_code == 422
        assert raised.value.detail[0]["loc"] == ["body", "hostname"]

    def should_refuse_to_give_a_logical_node_the_hostname_of_another(self, logical_nodes, telemetry):
        run(logical_nodes.create(new_logical_node("sw-01")))
        other = run(logical_nodes.create(new_logical_node("sw-02")))

        refused(logical_nodes.update(str(other.id), LogicalNode.model_validate({"hostname": "SW-01"})))

        assert telemetry.bumped == []

    def should_let_a_logical_node_keep_its_hostname_while_changing_the_rest(self, logical_nodes, db):
        node = run(logical_nodes.create(new_logical_node("sw-01")))

        run(logical_nodes.update(str(node.id), LogicalNode.model_validate({"hostname": "sw-01", "role": "edge"})))
        run(logical_nodes.update(str(node.id), LogicalNode.model_validate({"hostname": "SW-01"})))

        [stored] = rows(db, LogicalNode)
        assert (stored.hostname, stored.role) == ("SW-01", "edge")

    def should_not_look_for_a_duplicate_when_the_hostname_is_not_in_the_patch(self, logical_nodes):
        node = run(logical_nodes.create(new_logical_node("sw-01")))
        counted = CountingAdapter(logical_nodes.adapter)
        logical_nodes.adapter = counted

        run(logical_nodes.update(str(node.id), LogicalNode.model_validate({"role": "edge"})))

        assert counted.lookups == 0


class TestNodeInstances:
    def should_refuse_a_second_node_instance_for_a_logical_node(self, nodes, assets, logical_nodes):
        logical = run(logical_nodes.create(new_logical_node("sw-01")))
        first_asset = run(assets.create(new_asset("A1")))
        second_asset = run(assets.create(new_asset("B2")))
        first = run(nodes.create(Node(asset_ref_id=first_asset.id, logical_node_id=logical.id)))

        error = refused(nodes.create(Node(asset_ref_id=second_asset.id, logical_node_id=logical.id)))

        assert error.detail["resource"] == "node_instance"
        assert error.detail["field"] == "logical_node_id"
        assert error.detail["existing_id"] == first.id
        assert error.detail["message"] == f"Logical node sw-01 already has node instance {first.id}."

    def should_refuse_a_second_node_instance_on_an_asset(self, nodes, assets, logical_nodes, db):
        asset = run(assets.create(new_asset("A1")))
        first_logical = run(logical_nodes.create(new_logical_node("sw-01")))
        second_logical = run(logical_nodes.create(new_logical_node("sw-02")))
        first = run(nodes.create(Node(asset_ref_id=asset.id, logical_node_id=first_logical.id)))

        error = refused(nodes.create(Node(asset_ref_id=asset.id, logical_node_id=second_logical.id)))

        assert error.detail["resource"] == "node_instance"
        assert error.detail["field"] == "asset_ref_id"
        assert error.detail["existing_id"] == first.id
        assert error.detail["message"] == "Asset A1 is already used by sw-01."
        assert len(rows(db, Node)) == 1

    def should_refuse_a_second_node_instance_on_a_cluster(self, nodes, assets, logical_nodes, clusters):
        members = [run(assets.create(new_asset(serial))).id for serial in ("M1", "M2")]
        cluster = clusters.create_cluster(AssetClusterCreate(name="stack-1", asset_ids=members))
        first_logical = run(logical_nodes.create(new_logical_node("sw-01")))
        second_logical = run(logical_nodes.create(new_logical_node("sw-02")))
        first = run(
            nodes.create(
                Node(
                    asset_ref_id=cluster.id, asset_ref_type=AssetRefType.asset_cluster, logical_node_id=first_logical.id
                )
            )
        )

        error = refused(
            nodes.create(
                Node(
                    asset_ref_id=cluster.id,
                    asset_ref_type=AssetRefType.asset_cluster,
                    logical_node_id=second_logical.id,
                )
            )
        )

        assert error.detail["existing_id"] == first.id
        assert error.detail["message"] == "Cluster stack-1 is already used by sw-01."

    def should_not_mistake_a_cluster_for_an_asset_with_the_same_id(self, nodes, assets, logical_nodes, clusters, db):
        asset = run(assets.create(new_asset("A1")))
        cluster = clusters.create_cluster(AssetClusterCreate(name="stack-1", asset_ids=[]))
        assert asset.id == cluster.id  # the first of each kind
        first_logical = run(logical_nodes.create(new_logical_node("sw-01")))
        second_logical = run(logical_nodes.create(new_logical_node("sw-02")))

        run(nodes.create(Node(asset_ref_id=asset.id, logical_node_id=first_logical.id)))
        run(
            nodes.create(
                Node(
                    asset_ref_id=cluster.id,
                    asset_ref_type=AssetRefType.asset_cluster,
                    logical_node_id=second_logical.id,
                )
            )
        )

        assert len(rows(db, Node)) == 2

    def should_answer_404_for_an_asset_that_is_not_there(self, nodes, logical_nodes, db):
        logical = run(logical_nodes.create(new_logical_node("sw-01")))

        with pytest.raises(HTTPException) as raised:
            run(nodes.create(Node(asset_ref_id=999, logical_node_id=logical.id)))

        assert raised.value.status_code == 404
        assert rows(db, Node) == []

    def should_answer_404_for_a_logical_node_that_is_not_there(self, nodes, assets, db):
        asset = run(assets.create(new_asset("A1")))

        with pytest.raises(HTTPException) as raised:
            run(nodes.create(Node(asset_ref_id=asset.id, logical_node_id=999)))

        assert raised.value.status_code == 404
        assert "Logical node 999" in raised.value.detail
        assert rows(db, Node) == []

    def should_refuse_to_move_a_node_instance_to_a_logical_node_that_has_one(self, nodes, assets, logical_nodes):
        taken_asset = run(assets.create(new_asset("A1")))
        moving_asset = run(assets.create(new_asset("B2")))
        taken = run(logical_nodes.create(new_logical_node("sw-01")))
        run(nodes.create(Node(asset_ref_id=taken_asset.id, logical_node_id=taken.id)))
        free = run(logical_nodes.create(new_logical_node("sw-02")))
        moving = run(nodes.create(Node(asset_ref_id=moving_asset.id, logical_node_id=free.id)))

        refused(nodes.update(str(moving.id), move_to(taken.id)))

    def should_move_a_node_instance_to_a_free_logical_node(self, nodes, assets, logical_nodes, db):
        asset = run(assets.create(new_asset("A1")))
        first = run(logical_nodes.create(new_logical_node("sw-01")))
        node = run(nodes.create(Node(asset_ref_id=asset.id, logical_node_id=first.id)))
        free = run(logical_nodes.create(new_logical_node("sw-02")))

        run(nodes.update(str(node.id), move_to(free.id)))

        assert [n.logical_node_id for n in rows(db, Node)] == [free.id]

    def should_not_look_for_a_duplicate_when_the_logical_node_stays(self, nodes, assets, logical_nodes):
        asset = run(assets.create(new_asset("A1")))
        logical = run(logical_nodes.create(new_logical_node("sw-01")))
        node = run(nodes.create(Node(asset_ref_id=asset.id, logical_node_id=logical.id)))
        counted = CountingAdapter(nodes.adapter)
        nodes.adapter = counted

        run(nodes.update(str(node.id), move_to(logical.id)))

        assert counted.lookups == 0

    def should_refuse_to_move_a_node_instance_onto_an_asset_that_has_one(self, nodes, assets, logical_nodes):
        taken_asset = run(assets.create(new_asset("A1")))
        moving_asset = run(assets.create(new_asset("B2")))
        taken = run(logical_nodes.create(new_logical_node("sw-01")))
        run(nodes.create(Node(asset_ref_id=taken_asset.id, logical_node_id=taken.id)))
        other = run(logical_nodes.create(new_logical_node("sw-02")))
        moving = run(nodes.create(Node(asset_ref_id=moving_asset.id, logical_node_id=other.id)))

        error = refused(nodes.update(str(moving.id), move_to_asset(taken_asset.id)))

        assert error.detail["message"] == "Asset A1 is already used by sw-01."

    def should_move_a_node_instance_to_a_free_asset(self, nodes, assets, logical_nodes, db):
        asset = run(assets.create(new_asset("A1")))
        logical = run(logical_nodes.create(new_logical_node("sw-01")))
        node = run(nodes.create(Node(asset_ref_id=asset.id, logical_node_id=logical.id)))
        free = run(assets.create(new_asset("B2")))

        run(nodes.update(str(node.id), move_to_asset(free.id)))

        assert [n.asset_ref_id for n in rows(db, Node)] == [free.id]

    def should_answer_404_when_moving_onto_an_asset_that_is_not_there(self, nodes, assets, logical_nodes, db):
        asset = run(assets.create(new_asset("A1")))
        logical = run(logical_nodes.create(new_logical_node("sw-01")))
        node = run(nodes.create(Node(asset_ref_id=asset.id, logical_node_id=logical.id)))

        with pytest.raises(HTTPException) as raised:
            run(nodes.update(str(node.id), move_to_asset(999)))

        assert raised.value.status_code == 404
        assert [n.asset_ref_id for n in rows(db, Node)] == [asset.id]

    def should_not_look_for_a_duplicate_when_the_asset_stays(self, nodes, assets, logical_nodes):
        asset = run(assets.create(new_asset("A1")))
        logical = run(logical_nodes.create(new_logical_node("sw-01")))
        node = run(nodes.create(Node(asset_ref_id=asset.id, logical_node_id=logical.id)))
        counted = CountingAdapter(nodes.adapter)
        nodes.adapter = counted

        run(nodes.update(str(node.id), move_to_asset(asset.id)))  # as Change Asset sends it, unchanged
        run(nodes.update(str(node.id), TypeAdapter(Node).validate_python({"admin_status": "active"})))

        assert counted.lookups == 0

    def should_let_a_node_instance_that_already_shares_an_asset_be_edited(self, nodes, assets, logical_nodes, db):
        # What the migration leaves when it found shared assets: no unique index.
        with db.connection.engine.begin() as connection:
            connection.execute(text("DROP INDEX uq_node_asset_ref"))
        asset = run(assets.create(new_asset("A1")))
        first_logical = run(logical_nodes.create(new_logical_node("sw-01")))
        second_logical = run(logical_nodes.create(new_logical_node("sw-02")))
        with Session(db.connection.engine) as session:
            session.add(Node(asset_ref_id=asset.id, logical_node_id=first_logical.id))
            session.add(Node(asset_ref_id=asset.id, logical_node_id=second_logical.id))
            session.commit()
        first_id = rows(db, Node)[0].id
        patch = TypeAdapter(Node).validate_python(
            {"asset_ref_id": asset.id, "asset_ref_type": "asset", "admin_status": "active"}
        )

        run(nodes.update(str(first_id), patch))

        assert sorted(n.admin_status for n in rows(db, Node)) == ["active", "planned"]

    def should_answer_404_when_moving_to_a_logical_node_that_is_not_there(self, nodes, assets, logical_nodes):
        asset = run(assets.create(new_asset("A1")))
        logical = run(logical_nodes.create(new_logical_node("sw-01")))
        node = run(nodes.create(Node(asset_ref_id=asset.id, logical_node_id=logical.id)))

        with pytest.raises(HTTPException) as raised:
            run(nodes.update(str(node.id), move_to(999)))

        assert raised.value.status_code == 404


class TestRaces:
    """Two requests that both found nothing: the unique index refuses the second write."""

    def should_report_the_duplicate_the_index_found(self, assets, monkeypatch):
        first = run(assets.create(new_asset("ABC123")))
        real_find = uniqueness._find
        lookups = []

        async def blind_the_first_time(adapter, spec, value, exclude_id):
            lookups.append(value)
            return None if len(lookups) == 1 else await real_find(adapter, spec, value, exclude_id)

        monkeypatch.setattr(uniqueness, "_find", blind_the_first_time)

        error = refused(assets.create(new_asset("ABC123")))

        assert error.detail["existing_id"] == first.id
        assert len(lookups) == 2

    def should_report_the_asset_the_index_found(self, nodes, assets, logical_nodes, monkeypatch):
        asset = run(assets.create(new_asset("A1")))
        first_logical = run(logical_nodes.create(new_logical_node("sw-01")))
        second_logical = run(logical_nodes.create(new_logical_node("sw-02")))
        first = run(nodes.create(Node(asset_ref_id=asset.id, logical_node_id=first_logical.id)))
        real_find = uniqueness._find
        lookups = []

        async def blind_for_both_checks(adapter, spec, value, exclude_id):
            lookups.append(value)
            return None if len(lookups) <= 2 else await real_find(adapter, spec, value, exclude_id)

        monkeypatch.setattr(uniqueness, "_find", blind_for_both_checks)

        error = refused(nodes.create(Node(asset_ref_id=asset.id, logical_node_id=second_logical.id)))

        assert error.detail["field"] == "asset_ref_id"
        assert error.detail["existing_id"] == first.id

    def should_leave_any_other_integrity_error_alone(self, assets):
        class Failing(CountingAdapter):
            def create(self, asset):
                raise IntegrityError("INSERT", {}, Exception("NOT NULL constraint failed"))

        assets.adapter = Failing(assets.adapter)

        with pytest.raises(IntegrityError):
            run(assets.create(new_asset("ABC123")))


class TestOtherInventories:
    def should_leave_the_uniqueness_of_an_external_inventory_to_it(self):
        class External:
            def create(self, asset):
                return asset

            def query(self, filters):  # no extra_filters: nothing here could be asked for a duplicate
                raise AssertionError("an external inventory is not looked up")

        service = AssetService(
            AssetAdapter(External()), hardware_models=SimpleNamespace(enable_for_asset=lambda *a, **k: None)
        )

        created = run(service.create(new_asset("ABC123")))

        assert created.serial_number == "ABC123"


class TestIndexes:
    """What holds when something writes without going through the services."""

    @pytest.mark.parametrize(
        ("first", "second"),
        [
            (lambda: new_asset("ABC123"), lambda: new_asset(" abc123")),
            (lambda: new_logical_node("sw-01"), lambda: new_logical_node("SW-01 ")),
            (lambda: Node(asset_ref_id=1, logical_node_id=1), lambda: Node(asset_ref_id=2, logical_node_id=1)),
            (lambda: Node(asset_ref_id=1, logical_node_id=1), lambda: Node(asset_ref_id=1, logical_node_id=2)),
        ],
        ids=["asset", "logical node", "node instance of a logical node", "node instance on an asset"],
    )
    def should_refuse_a_duplicate(self, db, first, second):
        with Session(db.connection.engine) as session:
            session.add(first())
            session.commit()

        with Session(db.connection.engine) as session:
            session.add(second())
            with pytest.raises(IntegrityError):
                session.commit()


class TestOverHttp:
    """The request bodies the frontend sends: a PATCH carries every field it was shown, set or not."""

    @pytest.fixture
    def api(self, assets, logical_nodes, nodes):
        app = FastAPI()
        for prefix, service in (("assets", assets), ("logical_nodes", logical_nodes), ("node_instances", nodes)):
            app.add_api_route(f"/{prefix}", service.create, methods=["POST"], response_model=None)
            app.add_api_route(f"/{prefix}/{{id}}", service.update, methods=["PATCH"], response_model=None)
        return TestClient(app)

    ASSET = {"vendor": "cisco", "hardware_model": "C9300", "os": "cisco_iosxe"}

    def should_answer_409_with_the_record_in_the_way(self, api):
        first = api.post("/assets", json={**self.ASSET, "serial_number": "ABC123"}).json()

        response = api.post("/assets", json={**self.ASSET, "serial_number": " abc123"})

        assert response.status_code == 409
        assert response.json()["detail"]["existing_id"] == first["id"]
        assert response.json()["detail"]["code"] == "duplicate"

    def should_answer_422_for_a_blank_serial(self, api):
        response = api.post("/assets", json={**self.ASSET, "serial_number": "  "})

        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "serial_number"]

    def should_save_an_asset_the_way_the_frontend_does(self, api):
        first = api.post("/assets", json={**self.ASSET, "serial_number": "A1"}).json()
        other = api.post("/assets", json={**self.ASSET, "serial_number": "B2"}).json()

        unchanged = api.patch(f"/assets/{first['id']}", json={**first, "hardware_model": "C9300-48P"})
        taken = api.patch(f"/assets/{other['id']}", json={**other, "serial_number": "a1"})

        assert unchanged.status_code == 200
        assert taken.status_code == 409

    def should_save_a_logical_node_the_way_the_frontend_does(self, api):
        first = api.post("/logical_nodes", json={"hostname": "sw-01", "role": "core"}).json()
        other = api.post("/logical_nodes", json={"hostname": "sw-02", "role": "core"}).json()

        unchanged = api.patch(f"/logical_nodes/{first['id']}", json={**first, "role": "edge"})
        taken = api.patch(f"/logical_nodes/{other['id']}", json={**other, "hostname": "SW-01"})

        assert unchanged.status_code == 200
        assert taken.status_code == 409
        assert taken.json()["detail"]["existing_id"] == first["id"]

    def should_move_a_node_instance_the_way_the_frontend_does(self, api):
        first_asset = api.post("/assets", json={**self.ASSET, "serial_number": "A1"}).json()
        second_asset = api.post("/assets", json={**self.ASSET, "serial_number": "B2"}).json()
        taken = api.post("/logical_nodes", json={"hostname": "sw-01", "role": "core"}).json()
        free = api.post("/logical_nodes", json={"hostname": "sw-02", "role": "core"}).json()
        api.post("/node_instances", json={"asset_ref_id": first_asset["id"], "logical_node_id": taken["id"]})
        moving = api.post(
            "/node_instances", json={"asset_ref_id": second_asset["id"], "logical_node_id": free["id"]}
        ).json()

        response = api.patch(f"/node_instances/{moving['id']}", json={"logical_node_id": taken["id"]})

        assert response.status_code == 409
        assert response.json()["detail"]["resource"] == "node_instance"

    def should_answer_409_for_an_asset_that_has_a_node_instance(self, api):
        asset = api.post("/assets", json={**self.ASSET, "serial_number": "A1"}).json()
        first = api.post("/logical_nodes", json={"hostname": "sw-01", "role": "core"}).json()
        second = api.post("/logical_nodes", json={"hostname": "sw-02", "role": "core"}).json()
        node = api.post("/node_instances", json={"asset_ref_id": asset["id"], "logical_node_id": first["id"]}).json()

        response = api.post("/node_instances", json={"asset_ref_id": asset["id"], "logical_node_id": second["id"]})

        assert response.status_code == 409
        assert response.json()["detail"]["field"] == "asset_ref_id"
        assert response.json()["detail"]["existing_id"] == node["id"]
        assert response.json()["detail"]["message"] == "Asset A1 is already used by sw-01."

    def should_change_the_asset_the_way_the_frontend_does(self, api):
        taken_asset = api.post("/assets", json={**self.ASSET, "serial_number": "A1"}).json()
        moving_asset = api.post("/assets", json={**self.ASSET, "serial_number": "B2"}).json()
        free_asset = api.post("/assets", json={**self.ASSET, "serial_number": "C3"}).json()
        first = api.post("/logical_nodes", json={"hostname": "sw-01", "role": "core"}).json()
        second = api.post("/logical_nodes", json={"hostname": "sw-02", "role": "core"}).json()
        api.post("/node_instances", json={"asset_ref_id": taken_asset["id"], "logical_node_id": first["id"]})
        moving = api.post(
            "/node_instances", json={"asset_ref_id": moving_asset["id"], "logical_node_id": second["id"]}
        ).json()

        taken = api.patch(
            f"/node_instances/{moving['id']}", json={"asset_ref_id": taken_asset["id"], "asset_ref_type": "asset"}
        )
        free = api.patch(
            f"/node_instances/{moving['id']}", json={"asset_ref_id": free_asset["id"], "asset_ref_type": "asset"}
        )

        assert taken.status_code == 409
        assert free.status_code == 200
