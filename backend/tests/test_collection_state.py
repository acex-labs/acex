import asyncio
import base64
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from acex.api.routers.collection_agents import create_router
from acex.database import Connection, DatabaseManager
from acex.device_configs.device_config_manager import DeviceConfigManager
from acex.inventory.collection_agent_manager import CollectionAgentManager
from acex.inventory.node_service import NodeService
from acex.models import Asset, DeviceConfig, Node
from acex.models.collection_agent import CollectionAgent
from acex.models.collection_state import NodeCollectionState
from acex.models.logical_node import LogicalNode
from acex.plugins.adaptors.node_adapter import NodeAdapter
from acex.plugins.integrations.database import DatabasePlugin
from acex.utils import collection_state
from acex_devkit.models.collection_state import (
    CollectionFailure,
    CollectionResult,
    CollectionResultsUpload,
    CollectionStatus,
)
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session

T0 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = DatabaseManager(Connection(backend="sqlite", dbname="collection.db"))
    manager.create_tables()
    return manager


def add_node(db, hostname) -> int:
    with Session(db.connection.engine) as session:
        logical_node = LogicalNode(hostname=hostname, role="access", site="lab", sequence=1)
        asset = Asset(
            vendor="cisco",
            hardware_model="C9300",
            serial_number=f"SN-{hostname}",
            os="cisco_iosxe",
            os_version="17.9",
            ned_id="CiscoIOSCLIDriver",
        )
        session.add_all([logical_node, asset])
        session.flush()
        node = Node(asset_ref_id=asset.id, logical_node_id=logical_node.id)
        session.add(node)
        session.commit()
        return node.id


def add_agent(db, name="agent-1") -> int:
    with Session(db.connection.engine) as session:
        agent = CollectionAgent(name=name)
        session.add(agent)
        session.commit()
        return agent.id


def state(db, node_id):
    with Session(db.connection.engine) as session:
        return session.get(NodeCollectionState, node_id)


def fail(db, node_id, at, category=CollectionFailure.unreachable, message="Connection timed out"):
    with Session(db.connection.engine) as session:
        collection_state.record_failure(session, node_id, category, message, at)
        session.commit()


def succeed(db, node_id, at):
    with Session(db.connection.engine) as session:
        collection_state.record_success(session, node_id, at)
        session.commit()


def test_the_first_failure_says_since_when_and_why(db):
    node = add_node(db, "a")

    fail(db, node, T0)

    row = state(db, node)
    assert (row.consecutive_failures, row.failing_since, row.last_attempt_at, row.last_success_at) == (1, T0, T0, None)
    assert (row.category, row.message) == ("unreachable", "Connection timed out")


def test_a_second_failure_keeps_the_start_and_counts(db):
    node = add_node(db, "a")
    fail(db, node, T0)

    fail(db, node, T0 + timedelta(hours=1), CollectionFailure.authentication_failed, "Authentication failed")

    row = state(db, node)
    assert row.consecutive_failures == 2
    assert row.failing_since == T0
    assert row.last_attempt_at == T0 + timedelta(hours=1)
    assert row.category == "authentication_failed"


def test_a_success_clears_the_failure_and_a_later_failure_starts_over(db):
    node = add_node(db, "a")
    fail(db, node, T0)

    succeed(db, node, T0 + timedelta(hours=1))
    row = state(db, node)
    assert (row.consecutive_failures, row.failing_since, row.category, row.message) == (0, None, None, None)
    assert row.last_success_at == T0 + timedelta(hours=1)

    fail(db, node, T0 + timedelta(hours=2))
    row = state(db, node)
    assert row.failing_since == T0 + timedelta(hours=2)
    assert row.last_success_at == T0 + timedelta(hours=1)


def test_a_failure_without_a_category_is_other_and_a_long_message_is_cut(db):
    node = add_node(db, "a")

    with Session(db.connection.engine) as session:
        collection_state.record_failure(session, node, None, "x" * 900, T0)
        session.commit()

    row = state(db, node)
    assert row.category == "other"
    assert len(row.message) == 500


def test_the_agent_cannot_send_a_message_longer_than_the_limit():
    with pytest.raises(ValueError):
        CollectionResult(node_id=1, ok=False, message="x" * 501)


def test_report_results_records_each_node_and_names_the_unknown_ones(db):
    agent = add_agent(db)
    reachable, unreachable = add_node(db, "a"), add_node(db, "b")
    manager = CollectionAgentManager(db)

    answer = manager.report_results(
        agent,
        CollectionResultsUpload(
            results=[
                CollectionResult(node_id=reachable, ok=True),
                CollectionResult(
                    node_id=unreachable, ok=False, category=CollectionFailure.privilege_failed, message="m"
                ),
                CollectionResult(node_id=9999, ok=False),
            ]
        ),
    )

    assert (answer.accepted, answer.unknown_nodes) == (2, [9999])
    assert state(db, reachable).consecutive_failures == 0
    assert state(db, unreachable).category == "privilege_failed"
    assert state(db, 9999) is None


def test_a_node_named_twice_counts_once_with_its_last_result(db):
    agent = add_agent(db)
    node = add_node(db, "a")

    CollectionAgentManager(db).report_results(
        agent,
        CollectionResultsUpload(
            results=[
                CollectionResult(node_id=node, ok=False, category=CollectionFailure.unreachable),
                CollectionResult(node_id=node, ok=False, category=CollectionFailure.ssh_algorithm),
            ]
        ),
    )

    row = state(db, node)
    assert (row.consecutive_failures, row.category) == (1, "ssh_algorithm")


def test_the_node_says_which_agent_made_the_last_attempt(db, service):
    first, second = add_agent(db, "site-a"), add_agent(db, "site-b")
    node = add_node(db, "a")
    manager = CollectionAgentManager(db)
    failure = CollectionResultsUpload(results=[CollectionResult(node_id=node, ok=False)])
    success = CollectionResultsUpload(results=[CollectionResult(node_id=node, ok=True)])

    manager.report_results(first, failure)
    collection = listed(service)["a"].collection
    assert (collection.agent_id, collection.agent_name, collection.status) == (
        first,
        "site-a",
        CollectionStatus.failing,
    )

    manager.report_results(second, success)
    collection = listed(service)["a"].collection
    assert (collection.agent_id, collection.agent_name, collection.status) == (second, "site-b", CollectionStatus.ok)


def report_for_two_agents(db):
    first, second = add_agent(db, "site-a"), add_agent(db, "site-b")
    a, b, c, d, e = (add_node(db, name) for name in "abcde")
    manager = CollectionAgentManager(db)
    manager.report_results(
        first,
        CollectionResultsUpload(
            results=[
                CollectionResult(node_id=a, ok=True),
                CollectionResult(node_id=b, ok=False, category=CollectionFailure.unreachable),
                CollectionResult(node_id=c, ok=False, category=CollectionFailure.unreachable),
                CollectionResult(node_id=d, ok=False, category=CollectionFailure.ssh_algorithm),
                CollectionResult(node_id=e, ok=False),
            ]
        ),
    )
    manager.report_results(
        second,
        CollectionResultsUpload(
            results=[CollectionResult(node_id=a, ok=False, category=CollectionFailure.privilege_failed)]
        ),
    )
    return manager, first, second


def test_the_summary_of_an_agent_counts_its_nodes_by_why_they_were_not_collected(db):
    manager, first, second = report_for_two_agents(db)

    summary = manager.collection_summary(first)
    assert (summary.collected, summary.not_collected) == (0, 4)
    assert summary.by_category == {
        CollectionFailure.unreachable: 2,
        CollectionFailure.ssh_algorithm: 1,
        CollectionFailure.other: 1,
    }

    summary = manager.collection_summary(second)
    assert (summary.collected, summary.not_collected) == (0, 1)
    assert summary.by_category == {CollectionFailure.privilege_failed: 1}


def test_the_summary_of_an_agent_counts_collected_nodes_and_an_agent_with_none_is_empty(db):
    agent, idle = add_agent(db, "busy"), add_agent(db, "idle")
    first, second = add_node(db, "a"), add_node(db, "b")
    manager = CollectionAgentManager(db)
    manager.report_results(
        agent,
        CollectionResultsUpload(
            results=[CollectionResult(node_id=first, ok=True), CollectionResult(node_id=second, ok=True)]
        ),
    )

    assert (manager.collection_summary(agent).collected, manager.collection_summary(agent).not_collected) == (2, 0)
    assert manager.collection_summary(idle).model_dump() == {"collected": 0, "not_collected": 0, "by_category": {}}


def test_the_summary_of_an_agent_that_does_not_exist_is_refused(db):
    with pytest.raises(HTTPException) as refused:
        CollectionAgentManager(db).collection_summary(404)

    assert refused.value.status_code == 404


def test_the_summary_route_answers_with_the_counts(db):
    manager, first, _ = report_for_two_agents(db)
    app = FastAPI()
    app.include_router(create_router(SimpleNamespace(inventory=SimpleNamespace(collection_agent_manager=manager))))

    response = TestClient(app).get(f"/api/v1/inventory/collection_agents/{first}/collection")

    assert response.status_code == 200
    assert response.json() == {
        "collected": 0,
        "not_collected": 4,
        "by_category": {"unreachable": 2, "ssh_algorithm": 1, "other": 1},
    }


def test_the_node_list_can_be_filtered_on_the_agent_that_made_the_last_attempt(db, service):
    _, first, second = report_for_two_agents(db)

    assert set(listed(service, collection_agent_id=first)) == {"b", "c", "d", "e"}
    assert set(listed(service, collection_agent_id=second)) == {"a"}
    assert set(listed(service, collection_agent_id=first, collection_status="failing")) == {"b", "c", "d", "e"}
    assert set(listed(service, collection_agent_id=first, collection_status="ok")) == set()


def test_an_upload_does_not_take_the_agent_away(db):
    agent = add_agent(db)
    node = add_node(db, "a")
    CollectionAgentManager(db).report_results(
        agent, CollectionResultsUpload(results=[CollectionResult(node_id=node, ok=False)])
    )

    succeed(db, node, T0)

    assert state(db, node).agent_id == agent
    assert state(db, node).consecutive_failures == 0


def test_a_node_nobody_reported_on_has_no_agent(db, service):
    node = add_node(db, "a")
    succeed(db, node, T0)

    collection = listed(service)["a"].collection

    assert (collection.agent_id, collection.agent_name) == (None, None)


def test_results_from_an_agent_that_does_not_exist_are_refused(db):
    with pytest.raises(HTTPException) as refused:
        CollectionAgentManager(db).report_results(404, CollectionResultsUpload(results=[]))

    assert refused.value.status_code == 404


def test_the_results_route_answers_with_the_counts(db):
    agent = add_agent(db)
    node = add_node(db, "a")
    app = FastAPI()
    app.include_router(
        create_router(SimpleNamespace(inventory=SimpleNamespace(collection_agent_manager=CollectionAgentManager(db))))
    )

    response = TestClient(app).post(
        f"/api/v1/inventory/collection_agents/{agent}/results",
        json={"results": [{"node_id": node, "ok": False, "category": "unreachable", "message": "Timed out"}]},
    )

    assert response.status_code == 200
    assert response.json() == {"accepted": 1, "unknown_nodes": []}
    assert state(db, node).category == "unreachable"


def test_a_category_the_server_does_not_know_is_refused(db):
    agent = add_agent(db)
    node = add_node(db, "a")
    app = FastAPI()
    app.include_router(
        create_router(SimpleNamespace(inventory=SimpleNamespace(collection_agent_manager=CollectionAgentManager(db))))
    )

    response = TestClient(app).post(
        f"/api/v1/inventory/collection_agents/{agent}/results",
        json={"results": [{"node_id": node, "ok": False, "category": "made_up"}]},
    )

    assert response.status_code == 422


def upload(manager, node_id, text):
    payload = DeviceConfig(node_instance_id=str(node_id), content=base64.b64encode(text.encode()).decode())
    return asyncio.run(manager.upload_config(payload))


def test_an_uploaded_configuration_counts_as_a_collection_even_when_nothing_changed(db):
    node = add_node(db, "a")
    fail(db, node, T0)
    node_instance = SimpleNamespace(asset=SimpleNamespace(ned_id=None))
    inventory = SimpleNamespace(node_instances=SimpleNamespace(get=lambda _id: _awaitable(node_instance)))
    manager = DeviceConfigManager(db, inventory)

    upload(manager, node, "hostname a\n")
    row = state(db, node)
    assert (row.consecutive_failures, row.failing_since, row.category) == (0, None, None)
    assert row.last_success_at is not None

    fail(db, node, T0 + timedelta(days=1))
    with pytest.raises(HTTPException) as unchanged:
        upload(manager, node, "hostname a\n")

    assert unchanged.value.status_code == 409
    assert state(db, node).consecutive_failures == 0


async def _awaitable(value):
    return value


@pytest.fixture
def service(db):
    def get_asset(asset_id):
        with Session(db.connection.engine) as session:
            return session.get(Asset, asset_id)

    inventory = SimpleNamespace(assets=SimpleNamespace(adapter=SimpleNamespace(get=get_asset)))
    return NodeService(NodeAdapter(DatabasePlugin(db, Node)), inventory)


def listed(service, **kwargs):
    return {node.hostname: node for node in asyncio.run(service.query(**kwargs)).items}


def test_the_node_list_carries_the_collection_state_and_can_be_filtered_on_it(db, service):
    failing, collected, silent = (add_node(db, name) for name in ("failing", "collected", "silent"))
    fail(db, failing, T0, CollectionFailure.unreachable, "Connection timed out")
    succeed(db, collected, T0)

    everything = listed(service)

    assert everything["failing"].collection.status == CollectionStatus.failing
    assert everything["failing"].collection.category == CollectionFailure.unreachable
    assert everything["failing"].collection.failing_since is not None
    assert everything["collected"].collection.status == CollectionStatus.ok
    assert everything["silent"].collection is None
    assert set(listed(service, collection_status="failing")) == {"failing"}
    assert set(listed(service, collection_status="ok")) == {"collected"}
    assert set(listed(service, collection_status="unknown")) == {"silent"}
