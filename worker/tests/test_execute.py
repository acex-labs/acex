"""Operation handlers: execute runs a job's commands on its node and reports each output masked by the NED;
ping runs the abstract action and reports its result as is."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from acex_devkit.models.actions import PingParams, PingResult
from acex_devkit.models.credential import CredentialSecret
from acex_devkit.models.job import JobResponse
from acex_worker.handlers import execute
from acex_worker.handlers.execute import HandleExecute, HandlePing

JOB = JobResponse.model_validate(
    {
        "id": 9,
        "type": "acex.operations.execute",
        "data": {"node_id": 3, "commands": ["show version", "show run | i secret"]},
        "state": "running",
        "created_by": "alice",
        "created_at": "2026-10-23T00:00:00Z",
    }
)


class FakeSession:
    def __init__(self, driver: FakeDriver):
        self.driver = driver

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *exc) -> None:
        self.driver.closed = True

    async def execute(self, commands: list[str]) -> list[str]:
        if self.driver.fails:
            raise ConnectionError("unreachable")
        return [f"{command} -> enable secret 9 abc" for command in commands]

    async def ping(self, params: PingParams) -> PingResult:
        self.driver.pinged = params
        return PingResult(sent=params.count, received=params.count - 1, rtt_min_ms=1, rtt_avg_ms=2, rtt_max_ms=3)


class FakeDriver:
    def __init__(self, fails: bool = False):
        self.fails = fails
        self.closed = False
        self.session_args = None
        self.pinged = None

    def session(self, node, credentials):
        self.session_args = (node, credentials)
        return FakeSession(self)

    def mask(self, raw: str) -> str:
        return raw.replace("abc", "<REDACTED>")


def client() -> SimpleNamespace:
    node = SimpleNamespace(id=3, asset=SimpleNamespace(ned_id="CiscoIOSCLIDriver"), credentials=[SimpleNamespace(id=5)])
    secret = CredentialSecret(id=5, credential_type="userpass", fields={"username": "u", "password": "p"})
    inventory = SimpleNamespace(
        node_instances=SimpleNamespace(get=lambda node_id: node),
        credentials=SimpleNamespace(secret=lambda credential_id: secret),
    )
    return SimpleNamespace(inventory=inventory)


@pytest.fixture
def driver(monkeypatch) -> FakeDriver:
    driver = FakeDriver()
    monkeypatch.setattr(execute, "load_ned", lambda client, name: driver)
    return driver


def test_reports_each_command_masked(driver):
    response = HandleExecute().handle_hook(client(), JOB)

    assert response.success
    assert response.result == {
        "outputs": [
            {"command": "show version", "output": "show version -> enable secret 9 <REDACTED>"},
            {"command": "show run | i secret", "output": "show run | i secret -> enable secret 9 <REDACTED>"},
        ]
    }
    node, credentials = driver.session_args
    assert node.id == 3 and [c.id for c in credentials] == [5]
    assert driver.closed


def test_a_failed_session_fails_the_job(driver):
    driver.fails = True

    response = HandleExecute().handle_hook(client(), JOB)

    assert not response.success
    assert "unreachable" in response.error
    assert driver.closed


def test_ping_reports_the_abstract_result(driver):
    job = JOB.model_copy(
        update={
            "type": "acex.operations.actions.ping",
            "data": {"node_id": 3, "params": {"target": "10.0.0.1", "count": 4}},
        }
    )

    response = HandlePing().handle_hook(client(), job)

    assert response.success
    assert driver.pinged == PingParams(target="10.0.0.1", count=4)
    assert response.result == {
        "sent": 4,
        "received": 3,
        "rtt_min_ms": 1.0,
        "rtt_avg_ms": 2.0,
        "rtt_max_ms": 3.0,
        "success_rate": 75.0,
        "success": False,
    }
    assert driver.closed
