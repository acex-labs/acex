"""
The agents tell ACEX what they run: every ack carries the version of the agent's package, the commit its image was
built from and the branch that build ran on (the environment variables the image sets from its build arguments).

Only the client is replaced by a recorder; the agents' own ack code runs.
"""

import importlib.metadata
from types import SimpleNamespace

import pytest
from acex_collection_agent.agent import CollectionAgent
from acex_telemetry_agent.agent import TelemetryAgent


class _Recorder:
    def __init__(self):
        self.payloads = []

    def ack(self, id, payload):
        self.payloads.append((id, payload))


def _collection_agent(recorder: _Recorder) -> CollectionAgent:
    agent = object.__new__(CollectionAgent)  # the constructor would contact the API to log in
    agent.agent_id = 7
    agent.client = SimpleNamespace(inventory=SimpleNamespace(collection_agents=recorder))
    return agent


def _telemetry_agent(recorder: _Recorder, tmp_path) -> TelemetryAgent:
    client = SimpleNamespace(observability=SimpleNamespace(agents=recorder))
    return TelemetryAgent(client=client, agent_id=7, config_path=str(tmp_path / "telegraf.conf"))


def _ack(kind: str, recorder: _Recorder, tmp_path, revision: int):
    if kind == "collection":
        _collection_agent(recorder)._ack_manifest(revision)
    else:
        _telemetry_agent(recorder, tmp_path)._ack(revision)


PACKAGES = {"collection": "acex-collection-agent", "telemetry": "acex-telemetry-agent"}


@pytest.mark.parametrize("kind", ["collection", "telemetry"])
def test_the_ack_carries_the_package_version_and_the_build(kind, tmp_path, monkeypatch):
    monkeypatch.setenv("ACEX_BUILD_ID", "7f67e1d8e0eb3e23460e85f72d4c12550b0ea1d9")
    monkeypatch.setenv("ACEX_BUILD_REF", "dev")
    recorder = _Recorder()
    _ack(kind, recorder, tmp_path, revision=4)
    [(agent_id, payload)] = recorder.payloads
    assert agent_id == 7
    assert payload.config_revision == 4
    assert payload.agent_version == importlib.metadata.version(PACKAGES[kind])
    assert payload.build_id == "7f67e1d8e0eb3e23460e85f72d4c12550b0ea1d9"
    assert payload.build_ref == "dev"


@pytest.mark.parametrize("kind", ["collection", "telemetry"])
@pytest.mark.parametrize("value", [None, ""])
def test_an_image_without_a_build_reports_none(kind, value, tmp_path, monkeypatch):
    for name in ("ACEX_BUILD_ID", "ACEX_BUILD_REF"):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    recorder = _Recorder()
    _ack(kind, recorder, tmp_path, revision=1)
    [(_, payload)] = recorder.payloads
    assert payload.build_id is None
    assert payload.build_ref is None
    assert payload.agent_version == importlib.metadata.version(PACKAGES[kind])
