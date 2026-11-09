"""
Contract between agents/collection-agent and the NED interface of the drivers.

The collector opens a session on a driver (`driver.connect(address, credentials)`), reads the running config and
the neighbors through it, and uploads both through acex_client. These tests run the real Collector against
drivers built on the devkit's NetworkElementDriver with only the device and the ACEX API replaced, so a change
to the driver interface that the agent does not follow fails here instead of on a running stack.
"""

import asyncio
from types import SimpleNamespace

import pytest
from acex_client.exceptions import AcexHTTPError
from acex_collection_agent.collector import Collector
from acex_devkit.drivers import NetworkElementDriver, State, Transport
from acex_devkit.exceptions import AuthenticationFailed, ConnectionTimeout
from acex_devkit.models.agent_manifest import ManifestTarget
from acex_devkit.models.credential import CredentialSecret
from acex_devkit.models.lldp_neighbor import LldpNeighborEntry
from acex_driver_cisco_ioscli.cisco_ios_cli import CiscoIOSCLIDriver
from acex_driver_cisco_ioscli.transport.transport import CiscoIOSTransport

CONFIG = "hostname core-1\n!\nend\n"
NEIGHBOR = LldpNeighborEntry(local_interface="Gi1/0/1", remote_device="dist-1", remote_interface="Gi0/1")
LOGIN_SECRETS = {
    1: CredentialSecret(id=1, credential_type="userpass", fields={"username": "admin", "password": "pw"}),
    2: CredentialSecret(id=2, credential_type="privilege_escalation", fields={"password": "enable"}),
}


def make_driver(config=CONFIG, neighbors=(NEIGHBOR,), open_error=None, lldp=True):
    """A driver on the devkit's interface; `seen` records what the collector did to it."""
    seen = SimpleNamespace(address=None, credentials=None, opened=0, closed=0)

    class FakeTransport(Transport[str]):
        async def open(self):
            seen.address, seen.credentials, seen.opened = self.address, self.credentials, seen.opened + 1
            if open_error:
                raise open_error

        async def close(self):
            seen.closed += 1

        async def get_config(self):
            if isinstance(config, Exception):
                raise config
            return config

    class FakeState(State):
        async def get_lldp_neighbors(self, transport):
            if isinstance(neighbors, Exception):
                raise neighbors
            return list(neighbors)

    class FakeDriver(NetworkElementDriver):
        transport_class = FakeTransport
        state_class = FakeState if lldp else None

    return FakeDriver(), seen


class FakeClient:
    """The parts of acex_client.Acex the collector uses, recording what it uploads."""

    def __init__(self, driver, ned_id="FakeDriver", secrets=None, upload_error=None):
        self.fetched, self.config_uploads, self.neighbor_uploads = [], [], []
        secrets = LOGIN_SECRETS if secrets is None else secrets

        def secret(id):
            self.fetched.append(id)
            if id not in secrets:
                raise RuntimeError(f"no credential {id}")
            return secrets[id]

        def upload_observed(node_id, payload):
            if upload_error:
                raise upload_error
            self.config_uploads.append((node_id, payload.content))

        self.neds = SimpleNamespace(get_driver_instance=lambda name: driver if name == ned_id else None)
        self.inventory = SimpleNamespace(
            credentials=SimpleNamespace(secret=secret),
            node_instances=SimpleNamespace(upload_observed=upload_observed),
        )
        self.operations = SimpleNamespace(
            lldp=SimpleNamespace(upload=lambda payload: self.neighbor_uploads.append(payload))
        )


def target(**overrides):
    values = {
        "node_id": 7,
        "hostname": "core-1",
        "target_ip": "10.0.0.7",
        "ned_id": "FakeDriver",
        "credentials": {"userpass": 1, "privilege_escalation": 2, "snmp_community": 3},
    }
    return ManifestTarget(**{**values, **overrides})


def collect(client, *targets):
    return asyncio.run(Collector(client).collect_all(list(targets)))


def test_config_and_neighbors_are_collected_through_a_session():
    driver, seen = make_driver()
    client = FakeClient(driver)

    (result,) = collect(client, target())

    assert result["status"] == "ok"
    assert client.config_uploads == [("7", CONFIG)]
    (upload,) = client.neighbor_uploads
    assert upload.node_instance_id == 7
    assert [n.remote_device for n in upload.neighbors] == ["dist-1"]
    assert (seen.address, seen.opened, seen.closed) == ("10.0.0.7", 1, 1)


def test_the_transport_gets_the_login_credentials_and_nothing_else():
    driver, seen = make_driver()
    client = FakeClient(driver)

    collect(client, target())

    assert {c.credential_type for c in seen.credentials} == {"userpass", "privilege_escalation"}
    assert client.fetched == [1, 2]


def test_an_unchanged_config_is_reported_as_unchanged_and_the_neighbors_still_go_up():
    driver, _ = make_driver()
    client = FakeClient(driver, upload_error=AcexHTTPError(409, "unchanged"))

    (result,) = collect(client, target())

    assert result["status"] == "unchanged"
    assert len(client.neighbor_uploads) == 1


def test_a_driver_without_neighbor_support_still_collects_the_config():
    driver, _ = make_driver(lldp=False)
    client = FakeClient(driver)

    (result,) = collect(client, target())

    assert result["status"] == "ok"
    assert client.neighbor_uploads == []


def test_failing_neighbors_do_not_fail_the_collection():
    driver, _ = make_driver(neighbors=RuntimeError("cdp timed out"))
    client = FakeClient(driver)

    (result,) = collect(client, target())

    assert result["status"] == "ok"
    assert client.neighbor_uploads == []


@pytest.mark.parametrize(
    ("error", "message"),
    [(AuthenticationFailed("denied"), "Authentication failed"), (ConnectionTimeout("slow"), "Connection timed out")],
)
def test_connection_errors_are_reported_per_node(error, message):
    driver, _ = make_driver(open_error=error)
    client = FakeClient(driver)

    (result,) = collect(client, target())

    assert (result["status"], result["message"]) == ("error", message)
    assert client.config_uploads == []


def test_the_session_is_closed_when_the_config_cannot_be_read():
    driver, seen = make_driver(config=RuntimeError("boom"))

    (result,) = collect(FakeClient(driver), target())

    assert (result["status"], result["message"], seen.closed) == ("error", "boom", 1)


def test_an_empty_config_is_an_error_and_uploads_nothing():
    driver, seen = make_driver(config="")
    client = FakeClient(driver)

    (result,) = collect(client, target())

    assert (result["status"], result["message"], seen.closed) == ("error", "Empty config returned", 1)
    assert client.config_uploads == []


def test_a_login_that_cannot_be_fetched_stops_before_connecting():
    driver, seen = make_driver()

    (result,) = collect(FakeClient(driver, secrets={}), target())

    assert (result["status"], result["message"], seen.opened) == ("error", "Failed to fetch credentials", 0)


def test_one_node_failing_does_not_stop_the_others():
    driver, _ = make_driver()
    client = FakeClient(driver)

    results = collect(client, target(node_id=1, target_ip=None), target(node_id=2, ned_id="Missing"), target(node_id=3))

    assert [(r["node_id"], r["message"]) for r in results] == [
        (1, "No management IP"),
        (2, "NED 'Missing' not loaded"),
        (3, "Config uploaded"),
    ]


class OfflineIOSTransport(CiscoIOSTransport):
    """The real Cisco transport without the SSH session: the device's answers are canned."""

    async def open(self):
        self.credential("userpass")

    async def close(self):
        pass

    async def get_config(self):
        return CONFIG

    async def execute(self, request):
        lldp = "-" * 30 + "\nLocal Intf: Gi1/0/1\nPort id: Gi0/1\nSystem Name: dist-1\n"
        return [lldp if "lldp" in command else "% CDP is not enabled" for command in request]


class OfflineIOSDriver(CiscoIOSCLIDriver):
    transport_class = OfflineIOSTransport


def test_the_real_cisco_driver_is_collected_through_its_own_state():
    client = FakeClient(OfflineIOSDriver(), ned_id="CiscoIOSCLIDriver")

    (result,) = collect(client, target(ned_id="CiscoIOSCLIDriver"))

    assert result["status"] == "ok"
    assert client.config_uploads == [("7", CONFIG)]
    (upload,) = client.neighbor_uploads
    assert [(n.local_interface, n.remote_device, n.discovery_protocol) for n in upload.neighbors] == [
        ("Gi1/0/1", "dist-1", "lldp")
    ]
