"""The shared layout of the topology page: positions people saved, per container."""

import pytest
from acex.database import Connection, DatabaseManager
from acex.topology import TopologyPositions
from acex_devkit.models.topology import TopologyPosition


@pytest.fixture
def positions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = DatabaseManager(Connection(backend="sqlite", dbname="positions.db"))
    manager.create_tables()
    return TopologyPositions(manager)


def at(container, item, x, y) -> TopologyPosition:
    return TopologyPosition(container=container, item=item, x=x, y=y)


def placed(rows) -> dict[tuple[str, str], tuple[float, float]]:
    return {(r.container, r.item): (r.x, r.y) for r in rows}


class TestSaving:
    def should_keep_what_was_saved_and_who_saved_it(self, positions):
        positions.save([at("site:sto", "node:1", 10, 20)], updated_by="anna")

        [row] = positions.query()
        assert (row.container, row.item, row.x, row.y, row.updated_by) == ("site:sto", "node:1", 10, 20, "anna")
        assert row.updated_at is not None

    def should_move_an_item_saved_before(self, positions):
        positions.save([at("site:sto", "node:1", 10, 20)], updated_by="anna")
        positions.save([at("site:sto", "node:1", 30, 40)], updated_by="bo")

        assert placed(positions.query()) == {("site:sto", "node:1"): (30, 40)}
        assert positions.query()[0].updated_by == "bo"

    def should_leave_the_items_somebody_else_moved(self, positions):
        positions.save([at("site:sto", "node:1", 10, 20), at("site:sto", "node:2", 0, 0)], updated_by="anna")
        positions.save([at("site:sto", "node:2", 50, 60)], updated_by="bo")

        assert placed(positions.query()) == {("site:sto", "node:1"): (10, 20), ("site:sto", "node:2"): (50, 60)}

    def should_keep_one_item_in_two_containers_apart(self, positions):
        positions.save([at("site:sto", "node:1", 1, 1), at("site:upp", "node:1", 2, 2)], updated_by="anna")

        assert len(positions.query()) == 2

    def should_take_the_last_of_an_item_sent_twice(self, positions):
        positions.save([at("site:sto", "node:1", 1, 1), at("site:sto", "node:1", 2, 2)], updated_by="anna")

        assert placed(positions.query()) == {("site:sto", "node:1"): (2, 2)}


class TestListing:
    def should_give_the_named_containers_only(self, positions):
        positions.save(
            [at("site:sto", "node:1", 1, 1), at("site:upp", "node:2", 2, 2), at("site-boxes", "sto", 3, 3)],
            updated_by="anna",
        )

        assert set(placed(positions.query(container=["site:sto", "site-boxes"]))) == {
            ("site:sto", "node:1"),
            ("site-boxes", "sto"),
        }


class TestResetting:
    def should_forget_the_named_containers_only(self, positions):
        positions.save([at("site:sto", "node:1", 1, 1), at("site:upp", "node:2", 2, 2)], updated_by="anna")

        positions.reset(["site:sto"])

        assert set(placed(positions.query())) == {("site:upp", "node:2")}

    def should_forget_only_the_named_items_of_a_container(self, positions):
        positions.save(
            [at("site-boxes", "sto", 1, 1), at("site-boxes", "upp", 2, 2), at("site-boxes", "mmo", 3, 3)],
            updated_by="anna",
        )

        positions.reset(["site-boxes"], ["sto", "upp"])

        assert set(placed(positions.query())) == {("site-boxes", "mmo")}
