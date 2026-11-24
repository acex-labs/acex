"""The ztp provision handler pushes the node's full configuration to its approved device, with the bootstrap login of
the ZTP method it came in by, and then marks the node provisioned."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from acex_devkit.models.composed_configuration import ComposedConfiguration, System, SystemConfig
from acex_devkit.models.job import JobResponse
from acex_devkit.models.node_response import NodeProvisionStatus
from acex_worker.handlers import ztp_provision
from acex_worker.handlers.ztp_provision import HandleZtpProvision

JOB = JobResponse.model_validate(
    {
        "id": 8,
        "type": "acex.ztp.provision",
        "data": {"node_id": 3, "method": "cisco_iosxe_python"},
        "state": "running",
        "created_by": "alice",
        "created_at": "2026-11-24T00:00:00Z",
    }
)

PAYLOAD = "hostname core-1\n!\nvlan 10\n name MGMT\n!\n"


class FakeSession:
    def __init__(self, driver: FakeDriver):
        self.driver = driver

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *exc) -> None:
        pass

    async def apply(self, payload: str) -> str:
        self.driver.applied.append(payload)
        if self.driver.refuses:
            raise ConnectionError("the device closed the session")
        return "pushed, enable secret abc"


class FakeDriver:
    def __init__(self, refuses: bool = False):
        self.refuses = refuses
        self.applied: list[str] = []
        self.connected = []
        self.rendered = []

    def render(self, configuration, node):
        self.rendered.append((configuration, node))
        return SimpleNamespace(payload=PAYLOAD)

    def connect(self, address, credentials, node=None):
        self.connected.append((address, [c.fields for c in credentials], node))
        return FakeSession(self)

    def mask(self, raw: str) -> str:
        return raw.replace("abc", "<REDACTED>")


class FakeNode:
    def __init__(self):
        self.id = 3
        self.logical_node_id = 7
        self.asset = SimpleNamespace(ned_id="CiscoIOSCLIDriver")
        self.provision_status = NodeProvisionStatus.provisioning
        self.saved = []

    def save(self) -> None:
        self.saved.append(self.provision_status)


def method(login: tuple[str, str] | None = ("acex-ztp", "Temp123")):
    username, password = login or (None, None)
    return SimpleNamespace(bootstrap_username=username, bootstrap_password=password)


class FakeClient:
    def __init__(self, node: FakeNode, *, connections=None, bootstrap=None):
        self.desired = ComposedConfiguration(system=System(config=SystemConfig(hostname="core-1")))
        connections = [SimpleNamespace(primary=True, target_ip="10.1.2.3")] if connections is None else connections
        self.inventory = SimpleNamespace(
            node_instances=SimpleNamespace(get=lambda node_id: node),
            management_connections=SimpleNamespace(query=lambda *, node_id: SimpleNamespace(items=connections)),
            logical_nodes=SimpleNamespace(configuration=lambda *, id: SimpleNamespace(configuration=self.desired)),
        )
        bootstrap = method() if bootstrap is None else bootstrap
        self.ztp_methods = SimpleNamespace(get=lambda *, method: bootstrap)


@pytest.fixture
def driver(monkeypatch) -> FakeDriver:
    driver = FakeDriver()
    monkeypatch.setattr(ztp_provision, "load_ned", lambda client, name: driver)
    return driver


def test_the_full_configuration_is_pushed_to_the_primary_connection_with_the_bootstrap_login(driver):
    node = FakeNode()
    client = FakeClient(node)

    response = HandleZtpProvision().handle_hook(client, JOB)

    assert response.success, response.error
    assert driver.rendered == [(client.desired, node)]
    assert driver.connected == [("10.1.2.3", [{"username": "acex-ztp", "password": "Temp123"}], node)]
    assert driver.applied == [PAYLOAD]


def test_the_result_counts_the_lines_sent_and_masks_what_the_device_answered(driver):
    response = HandleZtpProvision().handle_hook(FakeClient(FakeNode()), JOB)

    assert response.result == {"lines_sent": 3, "output": "pushed, enable secret <REDACTED>"}


def test_the_node_is_provisioned_once_the_push_is_done(driver):
    node = FakeNode()

    HandleZtpProvision().handle_hook(FakeClient(node), JOB)

    assert node.provision_status == NodeProvisionStatus.provisioned
    assert node.saved == [NodeProvisionStatus.provisioned]


def test_a_push_that_fails_leaves_the_node_as_it_was(monkeypatch):
    driver = FakeDriver(refuses=True)
    monkeypatch.setattr(ztp_provision, "load_ned", lambda client, name: driver)
    node = FakeNode()

    response = HandleZtpProvision().handle_hook(FakeClient(node), JOB)

    assert not response.success
    assert "the device closed the session" in response.error
    assert node.saved == []
    assert node.provision_status == NodeProvisionStatus.provisioning


def test_a_node_without_a_primary_connection_fails_the_job(driver):
    client = FakeClient(FakeNode(), connections=[SimpleNamespace(primary=False, target_ip="10.1.2.4")])

    response = HandleZtpProvision().handle_hook(client, JOB)

    assert not response.success
    assert "Node 3 has no primary management connection with an IP" in response.error
    assert driver.connected == []


def test_a_method_without_a_bootstrap_login_fails_the_job(driver):
    client = FakeClient(FakeNode(), bootstrap=method(None))

    response = HandleZtpProvision().handle_hook(client, JOB)

    assert not response.success
    assert "No bootstrap login is set for ZTP method cisco_iosxe_python" in response.error
    assert driver.connected == []
