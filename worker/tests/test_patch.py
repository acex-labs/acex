"""Patch handlers: render reads the node live, diffs it within the job's path against the desired configuration
and reports the patch masked with a hash; apply sends the patch only if it still hashes as planned, then reads
the node again to verify. Every read is uploaded as the node's observed configuration."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from acex_devkit.drivers.example_ned import ExampleCodec
from acex_devkit.models.composed_configuration import ComposedConfiguration, Ntp, NtpServer, System, SystemConfig
from acex_devkit.models.job import JobResponse
from acex_worker.handlers import execute
from acex_worker.handlers.patch import HandlePatchApply, HandlePatchRender

PATCH = "hostname new\n"


def job(job_type: str, **data) -> JobResponse:
    return JobResponse.model_validate(
        {
            "id": 9,
            "type": job_type,
            "data": {"node_id": 3, **data},
            "state": "running",
            "created_by": "alice",
            "created_at": "2026-10-28T00:00:00Z",
        }
    )


class FakeSession:
    def __init__(self, device: FakeDevice):
        self.device = device

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *exc) -> None:
        pass

    async def get_config(self) -> str:
        return self.device.running

    async def apply(self, payload: str) -> str:
        self.device.applied.append(payload)
        if not self.device.ignores:
            self.device.running = payload + self.device.running.split("\n", 1)[1]
        return "ok, secret abc"


class FakeDevice:
    """A node running the example NED's syntax, which knows hostnames only."""

    def __init__(self, running: str = "hostname old\nenable secret abc\n", ignores: bool = False):
        self.running = running
        self.ignores = ignores
        self.applied: list[str] = []
        self.codec = ExampleCodec()

    def session(self, node, credentials) -> FakeSession:
        return FakeSession(self)

    def normalize(self, raw: str) -> str:
        return raw

    def mask(self, raw: str) -> str:
        return self.codec.mask(raw)

    def parse(self, raw: str, node):
        return self.codec.parse(raw, node)

    def render_patch(self, diff, node):
        return self.codec.render_patch(diff, node)


class FakeClient:
    def __init__(self, desired: ComposedConfiguration):
        self.uploads: list[str] = []
        node = SimpleNamespace(id=3, logical_node_id=7, asset=SimpleNamespace(ned_id="Example"), credentials=[])
        self.inventory = SimpleNamespace(
            node_instances=SimpleNamespace(
                get=lambda node_id: node, upload_observed=lambda id, payload: self.uploads.append(payload.content)
            ),
            logical_nodes=SimpleNamespace(configuration=lambda *, id: SimpleNamespace(configuration=desired)),
            credentials=SimpleNamespace(secret=lambda *, id: None),
        )


def desired(hostname: str = "new", ntp: list[str] = ()) -> ComposedConfiguration:
    servers = {address: NtpServer(address=address) for address in ntp}
    return ComposedConfiguration(system=System(config=SystemConfig(hostname=hostname), ntp=Ntp(servers=servers)))


@pytest.fixture
def device(monkeypatch) -> FakeDevice:
    device = FakeDevice()
    monkeypatch.setattr(execute, "load_ned", lambda client, name: device)
    return device


def render(client: FakeClient, path: str = "") -> dict:
    response = HandlePatchRender().handle_hook(client, job("acex.operations.patch.render", path=path))
    assert response.success, response.error
    return response.result


def apply(client: FakeClient, patch_hash: str) -> dict:
    data = {"plan_id": 5, "patch_hash": patch_hash, "path": ""}
    response = HandlePatchApply().handle_hook(client, job("acex.operations.patch.apply", **data))
    assert response.success, response.error
    return response.result


def test_render_reports_the_patch_its_hash_and_what_changes(device):
    client = FakeClient(desired())

    result = render(client)

    assert result["patch"] == PATCH
    assert result["patch_hash"] == hashlib.sha256(PATCH.encode()).hexdigest()
    assert result["changes"] == [{"op": "change", "path": "system.config", "attributes": ["hostname"]}]
    assert result["in_sync"] is False
    assert client.uploads == ["hostname old\nenable secret abc\n"]
    assert device.applied == []


def test_render_in_sync_has_no_patch(device):
    result = render(FakeClient(desired("old")))

    assert (result["patch"], result["patch_hash"], result["in_sync"]) == ("", None, True)


def test_render_reaches_only_its_path(device):
    assert render(FakeClient(desired()), path="system.ntp")["in_sync"] is True


def test_what_the_ned_cannot_write_is_left_out_and_listed(device):
    result = render(FakeClient(desired(ntp=["10.0.0.1"])))

    assert result["patch"] == PATCH
    assert result["unrendered"] == [{"op": "add", "path": "system.ntp.servers.10.0.0.1", "attributes": []}]


def test_a_node_with_only_what_its_ned_cannot_write_has_no_patch_and_is_not_in_sync(device):
    result = render(FakeClient(desired(ntp=["10.0.0.1"])), path="system.ntp")

    assert (result["patch"], result["patch_hash"], result["in_sync"]) == ("", None, False)


def test_apply_verifies_only_what_the_ned_can_write(device):
    client = FakeClient(desired(ntp=["10.0.0.1"]))

    result = apply(client, render(client)["patch_hash"])

    assert (result["outcome"], result["changes"]) == ("applied", [])
    assert [c["path"] for c in result["unrendered"]] == ["system.ntp.servers.10.0.0.1"]


def test_apply_sends_the_planned_patch_and_verifies_it(device):
    client = FakeClient(desired())

    result = apply(client, render(client)["patch_hash"])

    assert device.applied == [PATCH]
    assert result == {
        "outcome": "applied",
        "patch": PATCH,
        "output": "ok, secret <REDACTED>",
        "changes": [],
        "unrendered": [],
    }
    assert client.uploads[-1] == "hostname new\nenable secret abc\n"


def test_apply_sends_nothing_when_the_patch_changed_since_the_plan(device):
    planned = render(FakeClient(desired()))["patch_hash"]

    result = apply(FakeClient(desired("newer")), planned)

    assert device.applied == []
    assert result["outcome"] == "changed"
    assert result["changes"] == [{"op": "change", "path": "system.config", "attributes": ["hostname"]}]


def test_apply_reports_what_still_differs_after_the_patch(device):
    device.ignores = True
    client = FakeClient(desired())

    result = apply(client, render(client)["patch_hash"])

    assert device.applied == [PATCH]
    assert result["outcome"] == "residual"
    assert result["changes"] == [{"op": "change", "path": "system.config", "attributes": ["hostname"]}]
