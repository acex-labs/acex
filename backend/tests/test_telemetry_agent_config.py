"""Telemetry agent config flow: node scoping, per-capability coverage,
per-node error isolation, and last_config_poll semantics."""

import acex.inventory.inventory  # noqa: F401  — registers all SQLModel tables
import pytest
from acex.models.logical_node import LogicalNode
from acex.models.management_connections import ManagementConnection
from acex.models.node import Node
from acex.observability.agents.manager import TelemetryAgentManager
from acex.observability.agents.models import (
    TelemetryAgent,
    TelemetryAgentCapabilityLink,
    TelemetryAgentNodeLink,
)
from acex.observability.components.icmp_ping import IcmpPingTelemetry
from acex.observability.registry import TelemetryRegistry
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


class _Db:
    def __init__(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


class _CredentialManager:
    """Stub: raises for nodes in `broken`, records every lookup."""

    def __init__(self, broken: set[int] = frozenset()):
        self.broken = broken
        self.lookups: list[int] = []

    def get_node_community(self, node_id: int):
        self.lookups.append(node_id)
        if node_id in self.broken:
            raise HTTPException(status_code=503, detail="Vault unreachable")
        return None

    def get_site_community(self, site_name: str) -> str:
        return "public"


@pytest.fixture
def db():
    return _Db()


def _add_node(db, *, hostname: str, ip: str | None = "10.0.0.1", with_ln: bool = True) -> int:
    with Session(db.engine) as s:
        ln_id = 9999
        if with_ln:
            ln = LogicalNode(hostname=hostname, site="sto1")
            s.add(ln)
            s.flush()
            ln_id = ln.id
        node = Node(asset_ref_id=1, logical_node_id=ln_id)
        s.add(node)
        s.flush()
        if ip is not None:
            s.add(ManagementConnection(node_id=node.id, target_ip=ip))
        s.commit()
        return node.id


def _add_agent(db, *, node_ids: list[int], capabilities: list[str]) -> int:
    with Session(db.engine) as s:
        agent = TelemetryAgent(name="agent")
        s.add(agent)
        s.flush()
        for nid in node_ids:
            s.add(TelemetryAgentNodeLink(telemetry_agent_id=agent.id, node_id=nid))
        for cap in capabilities:
            s.add(TelemetryAgentCapabilityLink(telemetry_agent_id=agent.id, capability=cap))
        s.commit()
        return agent.id


def _last_poll(db, agent_id: int) -> str | None:
    with Session(db.engine) as s:
        return s.get(TelemetryAgent, agent_id).last_config_poll


def _manager(db, credential_manager=None) -> TelemetryAgentManager:
    return TelemetryAgentManager(db, telemetry_registry=TelemetryRegistry(db, credential_manager))


def _coverage(resp) -> dict[int, dict[str, tuple]]:
    """node_id -> {capability: (status, reason)} for compact assertions."""
    return {
        n.node_id: {str(cap): (c.status, c.reason) for cap, c in n.capabilities.items()} for n in resp.node_coverage
    }


def test_node_without_ip_is_reported_not_silently_dropped(db):
    ok = _add_node(db, hostname="r1", ip="10.0.0.1")
    no_ip = _add_node(db, hostname="r2", ip=None)
    agent_id = _add_agent(db, node_ids=[ok, no_ip], capabilities=["icmp", "snmp"])
    tam = _manager(db, _CredentialManager())

    config = tam.get_config(agent_id, reveal_secrets=True)
    assert 'node = "r1"' in config
    assert 'node = "r2"' not in config

    resp = tam.get(agent_id)
    assert [n.node_id for n in resp.node_coverage] == resp.resolved_nodes == sorted([ok, no_ip])
    assert {n.node_id: n.hostname for n in resp.node_coverage} == {ok: "r1", no_ip: "r2"}
    assert _coverage(resp) == {
        ok: {"icmp": ("rendered", None), "snmp": ("rendered", None)},
        no_ip: {"icmp": ("skipped", "no_management_ip"), "snmp": ("skipped", "no_management_ip")},
    }


def test_node_without_logical_node_is_reported(db):
    orphan = _add_node(db, hostname="x", with_ln=False)
    agent_id = _add_agent(db, node_ids=[orphan], capabilities=["icmp"])

    [n] = _manager(db).get(agent_id).node_coverage
    assert n.hostname is None
    assert n.capabilities["icmp"].reason == "no_logical_node"


def test_broken_credential_gives_partial_coverage(db):
    """ICMP still renders for a node whose SNMP credential is broken."""
    good = _add_node(db, hostname="good", ip="10.0.0.1")
    bad = _add_node(db, hostname="bad", ip="10.0.0.2")
    agent_id = _add_agent(db, node_ids=[good, bad], capabilities=["icmp", "snmp"])
    tam = _manager(db, _CredentialManager(broken={bad}))

    config = tam.get_config(agent_id, reveal_secrets=True)
    assert 'agents = ["udp://10.0.0.1:161"]' in config
    assert 'agents = ["udp://10.0.0.2:161"]' not in config
    assert 'urls = ["10.0.0.2"]' in config  # ping still rendered

    resp = tam.get(agent_id)
    assert _coverage(resp)[bad] == {"icmp": ("rendered", None), "snmp": ("skipped", "component_error")}
    [bad_cov] = [n for n in resp.node_coverage if n.node_id == bad]
    assert bad_cov.capabilities["snmp"].detail == "Vault unreachable"


def test_coverage_source_and_agent_level_capabilities(db):
    from acex_devkit.models.telemetry_agent import TelemetryAgentMatchRuleCreate

    explicit_only = _add_node(db, hostname="got-r1")
    both = _add_node(db, hostname="sto-r1")
    rule_only = _add_node(db, hostname="sto-r2")
    agent_id = _add_agent(db, node_ids=[explicit_only, both], capabilities=["icmp", "snmp_trap", "syslog_rfc5424"])
    with Session(db.engine) as s:
        s.get(LogicalNode, s.get(Node, explicit_only).logical_node_id).site = "got1"
        s.commit()
    tam = _manager(db)
    tam.add_rule(agent_id, TelemetryAgentMatchRuleCreate(site="sto"))

    resp = tam.get(agent_id)
    assert {n.node_id: n.source for n in resp.node_coverage} == {
        explicit_only: "explicit",
        both: "both",
        rule_only: "rule",
    }
    # Agent-level listeners are not per node.
    assert all(set(n.capabilities) == {"icmp"} for n in resp.node_coverage)


def test_ungranted_capability_provider_is_not_invoked(db):
    nid = _add_node(db, hostname="r1")
    agent_id = _add_agent(db, node_ids=[nid], capabilities=["icmp"])
    creds = _CredentialManager()

    config = _manager(db, creds).get_config(agent_id)
    assert "[[inputs.ping]]" in config
    assert "[[inputs.snmp]]" not in config
    assert creds.lookups == []


def test_only_agent_nodes_are_rendered(db):
    mine = _add_node(db, hostname="mine", ip="10.0.0.1")
    _add_node(db, hostname="other", ip="10.0.0.2")
    agent_id = _add_agent(db, node_ids=[mine], capabilities=["icmp"])

    config = _manager(db).get_config(agent_id)
    assert 'node = "mine"' in config
    assert 'node = "other"' not in config


def test_last_config_poll_set_only_after_successful_render(db):
    nid = _add_node(db, hostname="r1")
    agent_id = _add_agent(db, node_ids=[nid], capabilities=["icmp", "snmp_trap"])
    tam = _manager(db)

    # Agent-level trap credential with no credential manager → render fails.
    with Session(db.engine) as s:
        s.get(TelemetryAgent, agent_id).snmpv2c_credential_id = 1
        s.commit()
    with pytest.raises(HTTPException) as exc:
        tam.get_config(agent_id)
    assert exc.value.status_code == 400
    assert _last_poll(db, agent_id) is None

    with Session(db.engine) as s:
        s.get(TelemetryAgent, agent_id).snmpv2c_credential_id = None
        s.commit()
    tam.get_config(agent_id)
    assert _last_poll(db, agent_id) is not None


def test_listing_does_not_compute_coverage(db):
    nid = _add_node(db, hostname="r2", ip=None)
    _add_agent(db, node_ids=[nid], capabilities=["icmp"])

    [resp] = _manager(db).query()
    assert resp.node_coverage == []


def test_build_still_covers_all_nodes_for_global_views(db):
    a = _add_node(db, hostname="a", ip="10.0.0.1")
    b = _add_node(db, hostname="b", ip="10.0.0.2")

    pings = TelemetryRegistry(db).by_kind(IcmpPingTelemetry.kind)
    assert {p.node_id for p in pings} == {a, b}


def test_crud_paths_resolve_nodes_and_links(db):
    """Covers the select()/delete() paths: rules, links, capability swap, cascade delete."""
    from acex_devkit.models.telemetry_agent import TelemetryAgentMatchRuleCreate, TelemetryAgentUpdate

    sto = _add_node(db, hostname="sto-r1")
    agent_id = _add_agent(db, node_ids=[], capabilities=["icmp"])
    tam = _manager(db)

    rule = tam.add_rule(agent_id, TelemetryAgentMatchRuleCreate(site="sto"))
    assert tam.get(agent_id).resolved_nodes == [sto]
    tam.remove_rule(agent_id, rule.id)
    assert tam.get(agent_id).resolved_nodes == []

    tam.add_node(agent_id, sto)
    with pytest.raises(HTTPException) as exc:
        tam.add_node(agent_id, sto)
    assert exc.value.status_code == 409
    assert tam.query(node_id=sto)[0].id == agent_id
    tam.bump_revisions_for_node(sto)
    assert tam.get(agent_id).config_revision >= 1
    tam.remove_node(agent_id, sto)

    updated = tam.update(agent_id, TelemetryAgentUpdate(capabilities=["snmp"]))
    assert updated.capabilities == ["snmp"]
    assert [a.id for a in tam.query(capability="snmp")] == [agent_id]

    tam.delete(agent_id)
    assert tam.query() == []


def test_legacy_list_provider_is_scoped_by_target_node(db):
    mine = _add_node(db, hostname="mine")
    agent_id = _add_agent(db, node_ids=[mine], capabilities=["icmp"])

    registry = TelemetryRegistry(db)

    def legacy(db_manager):
        return [
            IcmpPingTelemetry(node_id=mine, hostname="legacy-mine", target_ip="192.0.2.1"),
            IcmpPingTelemetry(node_id=mine + 100, hostname="legacy-other", target_ip="192.0.2.2"),
        ]

    registry.register_provider(legacy)
    config = TelemetryAgentManager(db, telemetry_registry=registry).get_config(agent_id)
    assert 'node = "legacy-mine"' in config
    assert 'node = "legacy-other"' not in config


# --- Telegraf input fallback ---


@pytest.mark.parametrize(
    "node_kwargs, capabilities, expect_internal",
    [
        (None, ["icmp", "snmp"], True),  # agent with no nodes yet
        ({"ip": None}, ["icmp", "snmp"], True),  # all nodes skipped
        ({"ip": "10.0.0.1"}, ["icmp"], False),  # node input rendered
        (None, ["snmp_trap"], False),  # trap listener is an input
        (None, ["syslog_rfc5424"], False),  # syslog listener is an input
        (None, [], True),  # no capabilities at all
    ],
)
def test_internal_input_fallback_when_config_has_no_inputs(db, node_kwargs, capabilities, expect_internal):
    node_ids = [_add_node(db, hostname="r1", **node_kwargs)] if node_kwargs is not None else []
    agent_id = _add_agent(db, node_ids=node_ids, capabilities=capabilities)

    config = _manager(db).get_config(agent_id)
    assert ("[[inputs.internal]]" in config) is expect_internal
    assert "[[inputs." in config  # Telegraf never gets an input-less config


# --- config_revision bumps on node attribute changes ---


def _revision(db, agent_id: int) -> int:
    with Session(db.engine) as s:
        return s.get(TelemetryAgent, agent_id).config_revision


def _services(db):
    import asyncio
    from types import SimpleNamespace

    from acex.inventory.logical_node_service import LogicalNodeService
    from acex.inventory.node_service import NodeService
    from acex.plugins.adaptors.logical_node_adapter import LogicalNodeAdapter
    from acex.plugins.adaptors.node_adapter import NodeAdapter
    from acex.plugins.integrations.database import DatabasePlugin

    tam = _manager(db)
    ln_service = LogicalNodeService(
        LogicalNodeAdapter(DatabasePlugin(db, LogicalNode)),
        config_compiler=None,
        integrations=None,
        db_manager=db,
        telemetry_agent_manager=tam,
    )
    node_service = NodeService(NodeAdapter(DatabasePlugin(db, Node)), SimpleNamespace(telemetry_agent_manager=tam))
    return tam, ln_service, node_service, asyncio.run


def test_site_change_bumps_agents_gaining_and_losing_the_node(db):
    from acex_devkit.models.telemetry_agent import TelemetryAgentMatchRuleCreate

    nid = _add_node(db, hostname="r1")  # site "sto1"
    tam, ln_service, _, run = _services(db)
    sto = _add_agent(db, node_ids=[], capabilities=["icmp"])
    got = _add_agent(db, node_ids=[], capabilities=["icmp"])
    unrelated = _add_agent(db, node_ids=[], capabilities=["icmp"])
    tam.add_rule(sto, TelemetryAgentMatchRuleCreate(site="sto"))
    tam.add_rule(got, TelemetryAgentMatchRuleCreate(site="got"))
    tam.add_rule(unrelated, TelemetryAgentMatchRuleCreate(site="mal"))
    before = {a: _revision(db, a) for a in (sto, got, unrelated)}

    with Session(db.engine) as s:
        ln_id = s.get(Node, nid).logical_node_id
    run(ln_service.update(str(ln_id), LogicalNode(site="got1")))

    assert _revision(db, sto) == before[sto] + 1  # lost the node
    assert _revision(db, got) == before[got] + 1  # gained the node
    assert _revision(db, unrelated) == before[unrelated]
    with Session(db.engine) as s:
        ln = s.get(LogicalNode, ln_id)
        assert (ln.site, ln.hostname) == ("got1", "r1")  # partial update kept hostname
    assert tam.get(got).resolved_nodes == [nid]


def test_role_change_bumps_explicitly_linked_agent(db):
    nid = _add_node(db, hostname="r1")
    tam, ln_service, _, run = _services(db)
    agent_id = _add_agent(db, node_ids=[nid], capabilities=["icmp"])
    before = _revision(db, agent_id)

    with Session(db.engine) as s:
        ln_id = s.get(Node, nid).logical_node_id
    run(ln_service.update(str(ln_id), LogicalNode(role="access")))

    assert _revision(db, agent_id) == before + 1


def test_node_status_change_bumps_status_rule_agent(db):
    from acex_devkit.models.telemetry_agent import TelemetryAgentMatchRuleCreate

    nid = _add_node(db, hostname="r1")  # status "planned"
    tam, _, node_service, run = _services(db)
    agent_id = _add_agent(db, node_ids=[], capabilities=["icmp"])
    tam.add_rule(agent_id, TelemetryAgentMatchRuleCreate(status="active"))
    before = _revision(db, agent_id)

    run(node_service.update(str(nid), Node(status="active")))

    assert _revision(db, agent_id) == before + 1
    assert tam.get(agent_id).resolved_nodes == [nid]


def test_failed_update_does_not_bump(db):
    nid = _add_node(db, hostname="r1")
    tam, ln_service, _, run = _services(db)
    agent_id = _add_agent(db, node_ids=[nid], capabilities=["icmp"])
    before = _revision(db, agent_id)

    def boom(*_):
        raise RuntimeError("plugin down")

    ln_service.adapter.update = boom
    with Session(db.engine) as s:
        ln_id = s.get(Node, nid).logical_node_id
    with pytest.raises(RuntimeError):
        run(ln_service.update(str(ln_id), LogicalNode(site="got1")))

    assert _revision(db, agent_id) == before
