import warnings

import pytest
from acex.management_connections import ManagementConnectionManager
from acex.models import ManagementConnectionBase
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
