"""
The collection agent's loop around the drivers: it tells the client which NED interfaces it runs, says in its log when
a driver was left out, and tries the nodes that had no driver again soon instead of after the next full collection.

Only the client, the collector and the clock are replaced; the agent's own loop runs.
"""

import asyncio
import logging
import threading
import time as real_time
from types import SimpleNamespace

import pytest
from acex_client.exceptions import AcexHTTPError
from acex_collection_agent import agent as agent_module
from acex_collection_agent.agent import DRIVER_RETRY_SECONDS, POLL_INTERVAL, CollectionAgent, _as_collection_result
from acex_collection_agent.collector import SUPPORTED_NED_INTERFACES
from acex_devkit.models.agent_manifest import CollectionAgentManifest, ManifestTarget
from acex_devkit.models.collection_state import MESSAGE_LENGTH, CollectionFailure, CollectionResultsAccepted
from acex_devkit.models.ned import Ned

FIRST_NODE, SECOND_NODE = 1, 2


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def time(self):
        return self.now


class FakeCollector:
    """Records which nodes it was asked to collect, and has no driver for the nodes in `without_driver`."""

    def __init__(self):
        self.calls: list[list[int]] = []
        self.without_driver: set[int] = set()

    async def collect_all(self, targets, max_concurrent=20):
        self.calls.append([t.node_id for t in targets])
        return [
            {"node_id": t.node_id, "hostname": f"node-{t.node_id}", "status": "error", "message": "no driver"}
            | {"driver_unavailable": True, "category": CollectionFailure.driver_unavailable}
            if t.node_id in self.without_driver
            else {"node_id": t.node_id, "hostname": f"node-{t.node_id}", "status": "ok", "message": "Config uploaded"}
            for t in targets
        ]


def manifest(*node_ids: int, interval_seconds: int = 21600) -> CollectionAgentManifest:
    return CollectionAgentManifest(
        agent_id=7,
        name="agent",
        config_revision=1,
        interval_seconds=interval_seconds,
        targets=[ManifestTarget(node_id=n, ned_id="CiscoIOS", target_ip=f"10.0.0.{n}") for n in node_ids],
    )


@pytest.fixture
def clock(monkeypatch):
    fake = Clock()
    monkeypatch.setattr(agent_module, "time", fake)
    return fake


@pytest.fixture
def an_agent(monkeypatch):
    monkeypatch.setattr(agent_module, "Acex", lambda **kwargs: SimpleNamespace(**kwargs))
    agent = CollectionAgent("http://test", agent_id=7)
    agent.collector = FakeCollector()
    agent.synced = 0

    def count_syncs():
        agent.synced += 1

    agent._ensure_neds = count_syncs
    return agent


def run(agent, clock, monkeypatch, polls: int, manifest_at=lambda minutes: None):
    """Run the loop for `polls` polls of the manifest; `manifest_at(minutes)` says what the API answers then."""
    elapsed = {"polls": 0}
    started = clock.now

    async def sleep(seconds):
        clock.now += seconds
        elapsed["polls"] += 1
        if elapsed["polls"] >= polls:
            raise KeyboardInterrupt

    agent._fetch_manifest = lambda: manifest_at((clock.now - started) / 60)
    monkeypatch.setattr(agent_module.asyncio, "sleep", sleep)
    asyncio.run(agent._run())


def test_the_agent_names_the_ned_interfaces_it_runs(monkeypatch):
    monkeypatch.setattr(agent_module, "Acex", lambda **kwargs: SimpleNamespace(**kwargs))

    agent = CollectionAgent("http://test", agent_id=7)

    assert agent.client.ned_interfaces == SUPPORTED_NED_INTERFACES


def test_a_node_that_had_no_driver_is_tried_again_soon_and_the_others_are_left_alone(an_agent, clock, monkeypatch):
    an_agent.collector.without_driver = {SECOND_NODE}

    def api_answers(minutes):
        if minutes >= 6:
            an_agent.collector.without_driver = set()
        return manifest(FIRST_NODE, SECOND_NODE)

    run(an_agent, clock, monkeypatch, polls=20, manifest_at=api_answers)

    assert an_agent.collector.calls == [[FIRST_NODE, SECOND_NODE], [SECOND_NODE], [SECOND_NODE]]
    assert an_agent.synced == 3


def test_the_first_retry_comes_after_the_retry_interval_and_not_before(an_agent, clock, monkeypatch):
    an_agent.collector.without_driver = {SECOND_NODE}
    polls_before_the_retry = DRIVER_RETRY_SECONDS // POLL_INTERVAL

    run(an_agent, clock, monkeypatch, polls=polls_before_the_retry, manifest_at=lambda m: manifest(SECOND_NODE))
    assert an_agent.collector.calls == [[SECOND_NODE]]

    run(an_agent, clock, monkeypatch, polls=1, manifest_at=lambda m: manifest(SECOND_NODE))
    assert an_agent.collector.calls == [[SECOND_NODE], [SECOND_NODE]]


def test_nothing_is_tried_again_when_every_node_had_a_driver(an_agent, clock, monkeypatch):
    run(an_agent, clock, monkeypatch, polls=30, manifest_at=lambda m: manifest(FIRST_NODE, SECOND_NODE))

    assert an_agent.collector.calls == [[FIRST_NODE, SECOND_NODE]]
    assert an_agent.synced == 1


def test_a_retry_does_not_move_the_next_full_collection(an_agent, clock, monkeypatch):
    an_agent.collector.without_driver = {SECOND_NODE}

    run(
        an_agent,
        clock,
        monkeypatch,
        polls=35,
        manifest_at=lambda m: manifest(FIRST_NODE, SECOND_NODE, interval_seconds=1800),
    )

    full = [FIRST_NODE, SECOND_NODE]
    retries_every_five_minutes_until_the_half_hour = [[SECOND_NODE]] * 5
    assert an_agent.collector.calls == [full, *retries_every_five_minutes_until_the_half_hour, full]


def test_a_manifest_without_targets_is_still_reported(an_agent, clock, monkeypatch, caplog):
    with caplog.at_level(logging.INFO, logger="acex_collection_agent"):
        run(an_agent, clock, monkeypatch, polls=1, manifest_at=lambda m: manifest())

    assert "No targets in manifest, nothing to collect" in [r.getMessage() for r in caplog.records]
    assert an_agent.collector.calls == []


def test_a_node_that_left_the_manifest_is_not_waited_for(an_agent, clock, monkeypatch):
    an_agent.collector.without_driver = {SECOND_NODE}

    def api_answers(minutes):
        return manifest(FIRST_NODE, SECOND_NODE) if minutes < 1 else manifest(FIRST_NODE)

    run(an_agent, clock, monkeypatch, polls=20, manifest_at=api_answers)

    assert an_agent.collector.calls == [[FIRST_NODE, SECOND_NODE]]
    assert an_agent._waiting_for_driver == set()


class Reports:
    """Stands in for `client.inventory.collection_agents.report_results` and keeps what the agent sent."""

    def __init__(self):
        self.sent = []
        self.error = None
        self.unknown_nodes = []

    def __call__(self, id, payload):
        if self.error:
            raise self.error
        self.sent.append((id, [(r.node_id, r.ok, r.category, r.message) for r in payload.results]))
        return CollectionResultsAccepted(accepted=len(payload.results), unknown_nodes=self.unknown_nodes)


@pytest.fixture
def reports(an_agent):
    reports = Reports()
    an_agent.client.inventory = SimpleNamespace(collection_agents=SimpleNamespace(report_results=reports))
    return reports


def test_a_round_reports_every_node_once_with_what_was_found(an_agent, clock, monkeypatch, reports):
    an_agent.collector.without_driver = {SECOND_NODE}

    run(an_agent, clock, monkeypatch, polls=1, manifest_at=lambda m: manifest(FIRST_NODE, SECOND_NODE))

    assert reports.sent == [
        (7, [(FIRST_NODE, True, None, None), (SECOND_NODE, False, CollectionFailure.driver_unavailable, "no driver")])
    ]


def test_a_retry_reports_only_the_nodes_it_tried(an_agent, clock, monkeypatch, reports):
    an_agent.collector.without_driver = {SECOND_NODE}

    def api_answers(minutes):
        if minutes >= 6:
            an_agent.collector.without_driver = set()
        return manifest(FIRST_NODE, SECOND_NODE)

    run(an_agent, clock, monkeypatch, polls=20, manifest_at=api_answers)

    assert [[node for node, *_ in nodes] for _, nodes in reports.sent] == [
        [FIRST_NODE, SECOND_NODE],
        [SECOND_NODE],
        [SECOND_NODE],
    ]
    assert reports.sent[-1][1] == [(SECOND_NODE, True, None, None)]


def test_a_round_with_nothing_to_collect_reports_nothing(an_agent, clock, monkeypatch, reports):
    run(an_agent, clock, monkeypatch, polls=1, manifest_at=lambda m: manifest())

    assert reports.sent == []


def test_a_backend_that_cannot_take_the_report_does_not_stop_the_collection(
    an_agent, clock, monkeypatch, reports, caplog
):
    reports.error = AcexHTTPError(404, "Not Found")
    an_agent.collector.without_driver = {SECOND_NODE}

    def api_answers(minutes):
        if minutes >= 6:
            an_agent.collector.without_driver = set()
        return manifest(FIRST_NODE, SECOND_NODE)

    with caplog.at_level(logging.WARNING, logger="acex_collection_agent"):
        run(an_agent, clock, monkeypatch, polls=20, manifest_at=api_answers)

    assert an_agent.collector.calls == [[FIRST_NODE, SECOND_NODE], [SECOND_NODE], [SECOND_NODE]]
    assert any("Failed to report the collection results" in r.getMessage() for r in caplog.records)


def test_nodes_acex_does_not_know_are_said_in_the_log(an_agent, clock, monkeypatch, reports, caplog):
    reports.unknown_nodes = [SECOND_NODE]

    with caplog.at_level(logging.INFO, logger="acex_collection_agent"):
        run(an_agent, clock, monkeypatch, polls=1, manifest_at=lambda m: manifest(FIRST_NODE, SECOND_NODE))

    assert any("does not know these nodes" in r.getMessage() and "[2]" in r.getMessage() for r in caplog.records)


def test_a_message_longer_than_acex_takes_is_cut():
    result = _as_collection_result(
        {"node_id": 1, "status": "error", "message": "x" * 2000, "category": CollectionFailure.other}
    )

    assert len(result.message) == MESSAGE_LENGTH


def test_a_node_that_was_collected_unchanged_is_reported_as_collected():
    result = _as_collection_result({"node_id": 1, "status": "unchanged", "message": "Config not changed"})

    assert (result.ok, result.category, result.message) == (True, None, None)


def test_an_error_without_a_category_is_reported_without_one():
    result = _as_collection_result({"node_id": 1, "status": "error", "message": "boom"})

    assert (result.ok, result.category, result.message) == (False, None, "boom")


def ned(name="CiscoIOS", version="5.0.0") -> Ned:
    return Ned(
        name=name, package_name="acex-driver-cisco-ioscli", version=version, description="", filename="driver.whl"
    )


def an_agent_whose_neds(**neds) -> CollectionAgent:
    agent = object.__new__(CollectionAgent)  # the constructor would contact the API to log in
    agent._neds_synced = False
    agent.client = SimpleNamespace(neds=SimpleNamespace(**neds))
    return agent


def test_the_agent_says_all_neds_are_up_to_date_when_none_was_left_out(caplog):
    agent = an_agent_whose_neds(get_missing=lambda: [], incompatible={})

    with caplog.at_level(logging.INFO, logger="acex_collection_agent"):
        agent._ensure_neds()

    assert [r.getMessage() for r in caplog.records] == ["All NEDs up to date"]


def test_the_agent_does_not_say_all_neds_are_up_to_date_when_one_was_left_out(caplog):
    agent = an_agent_whose_neds(get_missing=lambda: [], incompatible={"CiscoIOS": "needs a newer agent"})

    with caplog.at_level(logging.INFO, logger="acex_collection_agent"):
        agent._ensure_neds()

    assert [r.getMessage() for r in caplog.records] == ["No NED to install; not used by this agent: CiscoIOS"]


def test_the_agent_gives_the_reason_when_an_installed_driver_is_not_usable(caplog):
    agent = an_agent_whose_neds(
        get_missing=lambda: [ned()],
        install=lambda n: True,
        get_driver_instance=lambda name: None,
        incompatible={"CiscoIOS": "CiscoIOS v5.0.0 could not be loaded: ImportError: no module named 'netmiko'"},
    )

    with caplog.at_level(logging.INFO, logger="acex_collection_agent"):
        agent._ensure_neds()

    assert (
        "NED CiscoIOS v5.0.0 installed but not usable: CiscoIOS v5.0.0 could not be loaded: ImportError"
        in "\n".join(r.getMessage() for r in caplog.records)
    )


def test_the_agent_still_says_when_a_driver_class_failed_to_load_without_saying_why(caplog):
    agent = an_agent_whose_neds(
        get_missing=lambda: [ned()], install=lambda n: True, get_driver_instance=lambda name: None, incompatible={}
    )

    with caplog.at_level(logging.INFO, logger="acex_collection_agent"):
        agent._ensure_neds()

    assert "NED CiscoIOS v5.0.0 installed but not usable: its driver class failed to load" in [
        r.getMessage() for r in caplog.records
    ]


class SlowRound:
    """A collector whose round lasts until the agent has acknowledged the manifest `acks_needed` times meanwhile."""

    def __init__(self, acks: list, acks_needed: int):
        self.acks, self.acks_needed = acks, acks_needed
        self.acks_when_it_ended = None

    async def collect_all(self, targets, max_concurrent=20):
        deadline = real_time.monotonic() + 5
        while len(self.acks) < self.acks_needed and real_time.monotonic() < deadline:
            await asyncio.to_thread(real_time.sleep, 0.005)
        self.acks_when_it_ended = len(self.acks)
        return [
            {"node_id": t.node_id, "hostname": "node", "status": "ok", "message": "Config uploaded"} for t in targets
        ]


def test_the_manifest_is_acknowledged_while_a_round_runs(an_agent, clock, monkeypatch):
    # The web interface calls an agent offline when its last acknowledgement is older than two minutes, and a round
    # over thousands of nodes takes longer than that. The poll in the loop waits for the round, so something else acks.
    acks = []
    monkeypatch.setattr(agent_module, "POLL_INTERVAL", 0.01)
    an_agent._ack_manifest = lambda revision: acks.append((revision, threading.current_thread().name))
    an_agent.collector = SlowRound(acks, acks_needed=3)

    run(an_agent, clock, monkeypatch, polls=1, manifest_at=lambda m: manifest(FIRST_NODE, SECOND_NODE))

    assert an_agent.collector.acks_when_it_ended >= 3
    assert {revision for revision, _ in acks} == {1}


def test_the_acknowledgements_of_a_round_do_not_wait_for_the_threads_the_round_uses(an_agent, clock, monkeypatch):
    acks = []
    monkeypatch.setattr(agent_module, "POLL_INTERVAL", 0.01)
    an_agent._ack_manifest = lambda revision: acks.append(threading.current_thread().name)
    an_agent.collector = SlowRound(acks, acks_needed=2)

    run(an_agent, clock, monkeypatch, polls=1, manifest_at=lambda m: manifest(FIRST_NODE))

    assert acks and set(acks) == {"acex-ack_0"}


def test_a_failing_acknowledgement_does_not_stop_the_round(an_agent, clock, monkeypatch, caplog):
    attempts = []

    def refuses(**kwargs):
        attempts.append(kwargs["id"])
        raise AcexHTTPError(503, "Unavailable")

    monkeypatch.setattr(agent_module, "POLL_INTERVAL", 0.01)
    an_agent.client.inventory = SimpleNamespace(collection_agents=SimpleNamespace(ack=refuses))
    an_agent.collector = SlowRound(attempts, acks_needed=2)

    with caplog.at_level(logging.WARNING, logger="acex_collection_agent"):
        run(an_agent, clock, monkeypatch, polls=1, manifest_at=lambda m: manifest(FIRST_NODE))

    assert an_agent.collector.acks_when_it_ended >= 2
    assert any("Failed to ack manifest" in r.getMessage() for r in caplog.records)
