"""The generated dashboards follow what the telemetry agents measure: one appears when some agent is granted its
capability and there are nodes to measure, and not before, so that nobody opens a board of panels that say "No data"."""

import acex.inventory.inventory  # noqa: F401  — registers all SQLModel tables
import pytest
from acex.models.logical_node import LogicalNode
from acex.models.management_connections import ManagementConnection
from acex.models.node import Node
from acex.observability.agents.models import TelemetryAgent, TelemetryAgentCapabilityLink
from acex.observability.capability import TelemetryCapability
from acex.observability.registry import TelemetryRegistry
from acex.observability.renderers.grafana.renderer import GrafanaRenderer
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

ICMP, SNMP = "acex-icmp-overview", "acex-snmp-overview"


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


@pytest.fixture
def db():
    return _Db()


@pytest.fixture
def renderer(db):
    return GrafanaRenderer(TelemetryRegistry(db))


def _add_node(db, hostname: str = "got-sw-1", ip: str = "192.0.2.1") -> int:
    with Session(db.engine) as s:
        logical = LogicalNode(hostname=hostname, site="got")
        s.add(logical)
        s.flush()
        node = Node(asset_ref_id=logical.id, logical_node_id=logical.id)
        s.add(node)
        s.flush()
        s.add(ManagementConnection(node_id=node.id, target_ip=ip))
        s.commit()
        return node.id


def _add_agent(db, *capabilities: str, name: str = "agent") -> int:
    with Session(db.engine) as s:
        agent = TelemetryAgent(name=name)
        s.add(agent)
        s.flush()
        for capability in capabilities:
            s.add(TelemetryAgentCapabilityLink(telemetry_agent_id=agent.id, capability=capability))
        s.commit()
        return agent.id


def _offered(renderer) -> set[str]:
    return {d["uid"] for d in renderer.list_dashboards()}


def test_no_agent_means_no_dashboard_even_with_nodes(db, renderer):
    _add_node(db)

    assert renderer.registry.granted_capabilities() == set()
    assert _offered(renderer) == set()
    for uid in (ICMP, SNMP):
        with pytest.raises(HTTPException) as refused:
            renderer.get_dashboard(uid)
        assert refused.value.status_code == 404


def test_an_agent_with_only_snmp_gives_the_snmp_dashboard_and_not_the_icmp_one(db, renderer):
    """The stage lab: its agent measures SNMP, and its devices cannot be pinged."""
    _add_node(db)
    _add_agent(db, "snmp")

    assert renderer.registry.granted_capabilities() == {TelemetryCapability.snmp}
    assert _offered(renderer) == {SNMP}
    assert renderer.get_dashboard(SNMP)["uid"] == SNMP
    with pytest.raises(HTTPException) as refused:
        renderer.get_dashboard(ICMP)
    assert refused.value.status_code == 404
    assert "icmp" in refused.value.detail


def test_the_icmp_dashboard_appears_when_an_agent_is_granted_icmp(db, renderer):
    _add_node(db)
    agent_id = _add_agent(db, "snmp")
    assert ICMP not in _offered(renderer)

    with Session(db.engine) as s:
        s.add(TelemetryAgentCapabilityLink(telemetry_agent_id=agent_id, capability="icmp"))
        s.commit()

    assert _offered(renderer) == {ICMP, SNMP}
    assert renderer.get_dashboard(ICMP)["uid"] == ICMP


def test_it_is_enough_that_one_of_several_agents_has_the_capability(db, renderer):
    _add_node(db)
    _add_agent(db, "snmp", name="a")
    _add_agent(db, "snmp", "icmp", name="b")
    _add_agent(db, "syslog_rfc5424", name="c")

    assert renderer.registry.granted_capabilities() == {
        TelemetryCapability.snmp,
        TelemetryCapability.icmp,
        TelemetryCapability.syslog_rfc5424,
    }
    assert _offered(renderer) == {ICMP, SNMP}


def test_a_granted_capability_without_nodes_has_nothing_to_show_yet(db, renderer):
    _add_agent(db, "icmp", "snmp")

    assert _offered(renderer) == {ICMP, SNMP}
    for uid in (ICMP, SNMP):
        with pytest.raises(HTTPException) as refused:
            renderer.get_dashboard(uid)
        assert refused.value.status_code == 404
        assert "no telemetry agent" not in refused.value.detail


def test_the_capability_of_an_agent_that_is_deleted_stops_counting(db, renderer):
    _add_node(db)
    agent_id = _add_agent(db, "icmp")
    assert _offered(renderer) == {ICMP}

    with Session(db.engine) as s:
        s.delete(s.get(TelemetryAgentCapabilityLink, (agent_id, "icmp")))
        s.delete(s.get(TelemetryAgent, agent_id))
        s.commit()

    assert _offered(renderer) == set()


def test_the_api_lists_what_grafana_sync_should_put_in_grafana(db, renderer):
    """grafana-sync reads this list, fetches each dashboard and removes the others from its folder."""
    from types import SimpleNamespace

    from acex.api.routers import observability
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    engine = SimpleNamespace(inventory=SimpleNamespace(grafana_renderer=renderer), influxdb_settings=None)
    app.include_router(observability.create_router(engine))
    client = TestClient(app)
    listing = "/api/v1/observability/grafana/dashboards"
    _add_node(db)

    assert client.get(listing).json() == []
    _add_agent(db, "snmp")
    assert [d["uid"] for d in client.get(listing).json()] == [SNMP]
    assert client.get(f"{listing}/{SNMP}").status_code == 200
    assert client.get(f"{listing}/{ICMP}").status_code == 404
