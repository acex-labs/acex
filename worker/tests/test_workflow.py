"""Workflow step handlers: steps on nodes render their templates per node from earlier artifacts, every step
computes the artifacts it names over its own result, assert fails the job when its checks don't hold, a
condition gives one answer, a probe pings from the worker, and a dry run reaches no device."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from acex_devkit.models.actions import PingParams, PingResult
from acex_devkit.models.credential import CredentialSecret
from acex_devkit.models.job import JobResponse
from acex_devkit.models.workflows import RunArtifact, WorkflowArtifacts, WorkflowRunDetail
from acex_worker.handlers import execute, workflow
from acex_worker.handlers.workflow import (
    HandleWorkflowAction,
    HandleWorkflowAssert,
    HandleWorkflowCompute,
    HandleWorkflowCondition,
    HandleWorkflowExecute,
    HandleWorkflowProbe,
    HandleWorkflowProbeAddress,
)

SHOW = "Cisco IOS XE Software, Version 17.09.04a\nGi1/0/1 up\nGi1/0/2 down\n"


def art(name, expression):
    return {"name": name, "expression": expression}


STEPS = {
    "show": {"type": "execute", "commands": ["show version"], "artifacts": [art("output", "result.output")]},
    "find": {"type": "compute", "artifacts": [art("version", "regex(output, 'Version (\\\\S+)')")]},
    "bounce": {
        "type": "execute",
        "commands": ["interface {column(down, 1)}", "! {version}"],
        "artifacts": [art("bounced", "count(result.output, 'ok')")],
    },
    "ping": {
        "type": "action",
        "params": {"target": "{version}", "count": 3, "vrf": "{nothing_yet}"},
        "artifacts": [art("reachable", "result.success")],
    },
    "down_ports": {"type": "compute", "artifacts": [art("down", "lines(output, 'down')"), art("n", "count(true)")]},
    "check": {"type": "assert", "checks": ["version == '17.09.04a'", "count(output, 'down') == 0"]},
    "up": {"type": "condition", "check": "all(reachable)", "artifacts": [art("went_up", "result.value")]},
    "per_node": {"type": "condition", "check": "reachable"},
    "probe": {"type": "probe", "artifacts": [art("alive", "result.success"), art("probed", "")]},
    "probe_at": {"type": "probe", "address": "10.9.9.{n}"},
    "typo": {"type": "assert", "checks": ["outptu contains 'x'"]},
    "nothing_yet": {"type": "compute", "artifacts": [art("nothing_yet", "1")]},
}

ARTIFACTS = {
    "output": RunArtifact(step="show", round=1, nodes={"acc-1": SHOW, "acc-2": SHOW.replace("down", "up")}),
    "down": RunArtifact(step="down_ports", round=1, nodes={"acc-1": ["Gi1/0/2 down"], "acc-2": []}),
    "version": RunArtifact(step="find", round=1, nodes={"acc-1": "17.09.04a"}),
    "reachable": RunArtifact(step="ping", round=1, nodes={"acc-1": True, "acc-2": False}),
    "n": RunArtifact(step="down_ports", round=1, value=7),
}


class FakeSession:
    def __init__(self, driver: FakeDriver):
        self.driver = driver

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *exc) -> None:
        pass

    async def execute(self, commands: list[str]) -> list[str]:
        self.driver.sent = commands
        return [f"{command} ok" for command in commands]

    async def ping(self, params: PingParams) -> PingResult:
        self.driver.sent = params
        return PingResult(sent=params.count, received=params.count)


class FakeDriver:
    sent = None

    def session(self, node, credentials):
        return FakeSession(self)

    def mask(self, raw: str) -> str:
        return raw


class FakeWorkflows:
    def __init__(self, mode: str):
        self.mode = mode
        self.asked: list[list[str]] = []

    def get_run(self, *, run_id: int) -> WorkflowRunDetail:
        nodes = [{"key": "start", "kind": "start"}, {"key": "end", "kind": "end"}]
        nodes += [{"key": key, "step": step, "targets": [1, 2]} for key, step in STEPS.items()]
        return WorkflowRunDetail.model_validate(
            {
                "id": run_id,
                "workflow_id": 1,
                "name": "wf",
                "mode": self.mode,
                "state": "running",
                "created_by": "alice",
                "created_at": "2026-10-24T00:00:00Z",
                "graph": {"nodes": nodes, "edges": []},
                "hostnames": {"1": "acc-1", "2": "acc-2"},
            }
        )

    def artifacts(self, *, run_id: int, names: list[str]) -> WorkflowArtifacts:
        self.asked.append(names)
        return WorkflowArtifacts(artifacts={name: ARTIFACTS[name] for name in names if name in ARTIFACTS})


def client(mode: str = "run") -> SimpleNamespace:
    node = SimpleNamespace(id=1, asset=SimpleNamespace(ned_id="Fake"), credentials=[])
    secret = CredentialSecret(id=5, credential_type="userpass", fields={})
    connection = SimpleNamespace(primary=True, target_ip="192.0.2.1")
    inventory = SimpleNamespace(
        node_instances=SimpleNamespace(get=lambda node_id: node),
        credentials=SimpleNamespace(secret=lambda *, id: secret),
        management_connections=SimpleNamespace(query=lambda node_id: SimpleNamespace(items=[connection])),
    )
    return SimpleNamespace(inventory=inventory, operations=SimpleNamespace(workflows=FakeWorkflows(mode)))


def job(key: str, node_id: int | None = 1) -> JobResponse:
    data = {"run_id": 7, "key": key, "round": 1} | ({"node_id": node_id} if node_id else {})
    return JobResponse.model_validate(
        {
            "id": 9,
            "type": "t",
            "data": data,
            "state": "running",
            "created_by": "a",
            "created_at": "2026-10-24T00:00:00Z",
        }
    )


@pytest.fixture
def driver(monkeypatch) -> FakeDriver:
    driver = FakeDriver()
    monkeypatch.setattr(execute, "load_ned", lambda client, name: driver)
    return driver


@pytest.fixture
def pinged(monkeypatch) -> list[str]:
    addresses = []

    def fake_ping(address, count, interval, timeout, privileged):
        addresses.append(address)
        return SimpleNamespace(packets_sent=count, packets_received=count, min_rtt=1.0, avg_rtt=1.5, max_rtt=2.0)

    monkeypatch.setattr(workflow, "ping", fake_ping)
    return addresses


def test_execute_renders_its_commands_for_the_node_and_leaves_its_artifacts(driver):
    response = HandleWorkflowExecute().handle_hook(client(), job("bounce"))
    assert response.success, response.error
    assert driver.sent == ["interface Gi1/0/2", "! 17.09.04a"]
    assert response.result["result"]["output"] == "interface Gi1/0/2 ok\n! 17.09.04a ok"
    assert response.result["artifacts"] == {"bounced": 2}


def test_a_dry_run_shows_what_would_be_sent_and_makes_no_artifacts(driver, pinged):
    response = HandleWorkflowExecute().handle_hook(client("dry_run"), job("bounce", node_id=2))
    assert response.result == {"result": {"dry_run": True, "commands": ["interface", "!"]}, "artifacts": {}}
    assert driver.sent is None
    ping = HandleWorkflowAction().handle_hook(client("dry_run"), job("ping"))
    assert ping.result["result"] == {
        "dry_run": True,
        "action": "ping",
        "target": "17.09.04a",
        "count": 3,
        "vrf": None,
        "source": None,
        "timeout": 2,
        "size": None,
    }
    assert HandleWorkflowProbe().handle_hook(client("dry_run"), job("probe")).result["result"]["address"] == "192.0.2.1"
    assert pinged == []


def test_an_action_renders_its_params_and_leaves_its_artifacts(driver):
    response = HandleWorkflowAction().handle_hook(client(), job("ping"))
    assert response.success, response.error
    assert driver.sent == PingParams(target="17.09.04a", count=3)
    assert response.result["result"]["success_rate"] == 100.0 and response.result["artifacts"] == {"reachable": True}


def test_a_probe_pings_from_acex_to_the_node_or_an_address(pinged):
    response = HandleWorkflowProbe().handle_hook(client(), job("probe"))
    assert response.success, response.error
    assert response.result["result"]["address"] == "192.0.2.1" and response.result["artifacts"]["alive"] is True
    assert response.result["artifacts"]["probed"] == response.result["result"]  # no expression: all of it
    once = HandleWorkflowProbeAddress().handle_hook(client(), job("probe_at", node_id=None))
    assert once.success, once.error
    assert pinged == ["192.0.2.1", "10.9.9.7"] and once.result["result"]["rtt_avg_ms"] == 1.5


def test_compute_leaves_per_node_values_or_one():
    response = HandleWorkflowCompute().handle_hook(client(), job("down_ports", node_id=None))
    assert response.success, response.error
    down, n = response.result["artifacts"]["down"], response.result["artifacts"]["n"]
    assert down == {"value": None, "nodes": {"acc-1": ["Gi1/0/2 down"], "acc-2": []}}
    assert n == {"value": 0, "nodes": None}


def test_assert_fails_the_job_naming_the_nodes_it_failed_on():
    response = HandleWorkflowAssert().handle_hook(client(), job("check", node_id=None))
    assert not response.success
    assert response.error == (
        "All checks must pass. Failed:\n"
        "count(output, 'down') == 0  on acc-1\n"
        '  acc-1: output = "Cisco IOS XE Software, Version 17.09.04a\\nGi1/0/1 up\\nGi1/0/2 down\\n"'
    )


def test_a_condition_gives_one_answer():
    response = HandleWorkflowCondition().handle_hook(client(), job("up", node_id=None))
    assert response.result == {
        "result": {"value": False, "inputs": {"acc-1": {"reachable": True}, "acc-2": {"reachable": False}}},
        "artifacts": {"went_up": {"value": False, "nodes": None}},
    }
    refused = HandleWorkflowCondition().handle_hook(client(), job("per_node", node_id=None))
    assert not refused.success and "reads reachable per node" in refused.error
    dry = HandleWorkflowCondition().handle_hook(client("dry_run"), job("up", node_id=None))
    assert dry.result["result"] == {"dry_run": True}


def test_an_artifact_no_step_makes_is_refused_even_in_a_dry_run():
    response = HandleWorkflowAssert().handle_hook(client("dry_run"), job("typo", node_id=None))
    assert not response.success and "No artifact outptu in this workflow" in response.error
