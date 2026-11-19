"""A neighbor is matched to a node of the inventory by the name it reports, in whatever case and padding."""

import pytest
from acex.database import Connection, DatabaseManager
from acex.lldp.lldp_neighbor_manager import LldpNeighborManager
from acex.models import LogicalNode, Node
from acex_devkit.models.lldp_neighbor import LldpNeighborEntry, LldpNeighborUpload
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = DatabaseManager(Connection(backend="sqlite", dbname="lldp.db"))
    manager.create_tables()
    return manager


@pytest.fixture
def manager(db):
    return LldpNeighborManager(db)


def add_node(db, hostname) -> int:
    with Session(db.connection.engine) as session:
        logical_node = LogicalNode(hostname=hostname, role="core", site="lab")
        session.add(logical_node)
        session.commit()
        node = Node(asset_ref_id=logical_node.id, logical_node_id=logical_node.id)
        session.add(node)
        session.commit()
        return node.id


def upload(manager, node_id, *remote_devices):
    neighbors = [
        LldpNeighborEntry(local_interface=f"Gi1/0/{i}", remote_device=name, remote_interface="Gi1/0/1")
        for i, name in enumerate(remote_devices, start=1)
    ]
    return manager.upload_neighbors(LldpNeighborUpload(node_instance_id=node_id, neighbors=neighbors))


def resolved(manager, node_id) -> dict[str, int | None]:
    return {row.remote_device: row.remote_node_id for row in manager.get_neighbors(node_id)}


class TestResolvingANeighbor:
    def should_match_the_name_as_it_is_stored(self, db, manager):
        reporter, core = add_node(db, "access-1"), add_node(db, "core-sw1")

        upload(manager, reporter, "core-sw1")

        assert resolved(manager, reporter) == {"core-sw1": core}

    @pytest.mark.parametrize("reported", ["CORE-SW1", "Core-Sw1", "  core-sw1 "])
    def should_match_a_name_in_another_case_or_with_padding(self, db, manager, reported):
        reporter, core = add_node(db, "access-1"), add_node(db, "core-sw1")

        upload(manager, reporter, reported)

        assert resolved(manager, reporter) == {reported: core}

    def should_match_a_name_stored_in_another_case_than_it_is_reported(self, db, manager):
        reporter, core = add_node(db, "access-1"), add_node(db, "Core-SW1")

        upload(manager, reporter, "core-sw1")

        assert resolved(manager, reporter) == {"core-sw1": core}

    @pytest.mark.parametrize("reported", ["core-sw1.example.com", "CORE-SW1.example.com"])
    def should_match_the_name_without_its_domain(self, db, manager, reported):
        reporter, core = add_node(db, "access-1"), add_node(db, "core-sw1")

        upload(manager, reporter, reported)

        assert resolved(manager, reporter) == {reported: core}

    def should_leave_a_name_nobody_has_unresolved(self, db, manager):
        reporter = add_node(db, "access-1")
        add_node(db, "core-sw1")

        upload(manager, reporter, "core-sw2", "core-sw1x")

        assert resolved(manager, reporter) == {"core-sw2": None, "core-sw1x": None}

    def should_prefer_the_exact_name_when_two_differ_only_in_case(self, db, manager):
        reporter = add_node(db, "access-1")
        lower = add_node(db, "core-sw1")
        try:
            upper = add_node(db, "CORE-SW1")
        except IntegrityError:
            pytest.skip("two hostnames that differ only in case cannot exist once the inventory keeps hostnames unique")

        upload(manager, reporter, "CORE-SW1", "core-sw1")

        assert resolved(manager, reporter) == {"CORE-SW1": upper, "core-sw1": lower}

    def should_resolve_a_neighbor_that_was_unresolved_when_the_same_set_arrives_again(self, db, manager):
        reporter = add_node(db, "access-1")
        upload(manager, reporter, "CORE-SW1")
        assert resolved(manager, reporter) == {"CORE-SW1": None}

        core = add_node(db, "core-sw1")
        with pytest.raises(HTTPException) as unchanged:
            upload(manager, reporter, "CORE-SW1")

        assert unchanged.value.status_code == 409
        assert resolved(manager, reporter) == {"CORE-SW1": core}
