import warnings
from types import SimpleNamespace

import pytest
from acex.api.routers.management_connections import create_router
from acex.constants import BASE_URL
from acex.management_connections import ManagementConnectionManager
from acex.models import ManagementConnectionBase
from acex_devkit.models.management_connection import ManagementConnectionUpdate
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


@pytest.fixture(autouse=True)
def deprecations_are_errors():
    with warnings.catch_warnings():
        warnings.filterwarnings("error", category=DeprecationWarning, module=r"acex\.management_connections")
        yield


@pytest.fixture
def manager():
    return ManagementConnectionManager(_Db())


def add(manager, node_id, target_ip, primary=False):
    return manager.create_connection(ManagementConnectionBase(node_id=node_id, target_ip=target_ip, primary=primary))


def test_a_created_connection_can_be_fetched(manager):
    created = add(manager, 1, "10.0.0.1", primary=True)

    fetched = manager.get_connection(created.id)

    assert fetched == created
    assert (fetched.node_id, fetched.target_ip, fetched.primary) == (1, "10.0.0.1", True)


def test_a_missing_connection_is_none(manager):
    assert manager.get_connection(99) is None


def test_connections_can_be_filtered_by_node(manager):
    add(manager, 1, "10.0.0.1")
    add(manager, 2, "10.0.0.2")
    add(manager, 1, "10.0.0.3")

    assert sorted(c.target_ip for c in manager.list_connections(node_id=1)) == ["10.0.0.1", "10.0.0.3"]
    assert len(manager.list_connections()) == 3


def test_limit_and_offset_page_through_the_connections(manager):
    for last_octet in range(1, 5):
        add(manager, 1, f"10.0.0.{last_octet}")

    first = manager.list_connections(limit=2, offset=0)
    second = manager.list_connections(limit=2, offset=2)

    assert len(first) == len(second) == 2
    assert {c.id for c in first}.isdisjoint({c.id for c in second})


def test_a_connection_can_be_deleted(manager):
    created = add(manager, 1, "10.0.0.1")

    assert manager.delete_connection(created.id) is True
    assert manager.get_connection(created.id) is None


def test_deleting_a_missing_connection_returns_false(manager):
    assert manager.delete_connection(99) is False


def test_an_update_changes_only_the_fields_that_are_sent(manager):
    created = add(manager, 1, "10.0.0.1", primary=True)

    updated = manager.update_connection(created.id, ManagementConnectionUpdate(target_ip="10.0.0.9"))

    assert (updated.target_ip, updated.primary, updated.connection_type) == ("10.0.0.9", True, created.connection_type)
    assert manager.get_connection(created.id) == updated


def test_a_field_sent_as_null_stays_as_it_is(manager):
    created = add(manager, 1, "10.0.0.1", primary=True)

    updated = manager.update_connection(created.id, ManagementConnectionUpdate(target_ip=None, primary=None))

    assert (updated.target_ip, updated.primary) == ("10.0.0.1", True)


def test_making_a_connection_primary_makes_the_other_connections_of_its_node_give_way(manager):
    first = add(manager, 1, "10.0.0.1", primary=True)
    second = add(manager, 1, "10.0.0.2")
    other_node = add(manager, 2, "10.0.1.1", primary=True)

    manager.update_connection(second.id, ManagementConnectionUpdate(primary=True))

    assert manager.get_connection(second.id).primary is True
    assert manager.get_connection(first.id).primary is False
    assert manager.get_connection(other_node.id).primary is True


def test_demoting_a_connection_leaves_the_others_alone(manager):
    first = add(manager, 1, "10.0.0.1", primary=True)
    second = add(manager, 1, "10.0.0.2")

    manager.update_connection(first.id, ManagementConnectionUpdate(primary=False))

    assert (manager.get_connection(first.id).primary, manager.get_connection(second.id).primary) == (False, False)


def test_updating_a_missing_connection_is_a_404(manager):
    with pytest.raises(HTTPException) as refused:
        manager.update_connection(99, ManagementConnectionUpdate(primary=True))

    assert refused.value.status_code == 404


def test_the_api_accepts_a_patch_of_a_connection(manager):
    first = add(manager, 1, "10.0.0.1", primary=True)
    second = add(manager, 1, "10.0.0.2")
    app = FastAPI()
    app.include_router(create_router(SimpleNamespace(mgmt_con_manager=manager)))
    client = TestClient(app)

    changed = client.patch(f"{BASE_URL}/inventory/management_connections/{second.id}", json={"primary": True})
    missing = client.patch(f"{BASE_URL}/inventory/management_connections/99", json={"primary": True})

    assert changed.status_code == 200
    assert (changed.json()["id"], changed.json()["primary"]) == (second.id, True)
    assert manager.get_connection(first.id).primary is False
    assert missing.status_code == 404
