import builtins
import logging
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from acex.models.asset import Asset
from acex.models.logical_node import LogicalNode
from acex.models.node import Node
from acex.models.regions import SiteRegionAssignment
from acex.observability.agents.models import (
    TelemetryAgent,
    TelemetryAgentCapabilityLink,
    TelemetryAgentMatchRule,
    TelemetryAgentNodeLink,
)
from acex.observability.capability import TelemetryCapability
from acex.observability.components.base import TelemetryComponent
from acex.observability.registry import AgentComponents
from acex.utils.agent_node_links import set_agent_nodes
from acex_devkit.models.agent_manifest import AckResult, AgentNodeSet, AgentNodeSetResult
from acex_devkit.models.telemetry_agent import (
    InfluxDBVersion,
    NodeCoverage,
    TelemetryAgentAck,
    TelemetryAgentCreate,
    TelemetryAgentMatchRuleCreate,
    TelemetryAgentMatchRuleResponse,
    TelemetryAgentResponse,
    TelemetryAgentUpdate,
)
from fastapi import HTTPException
from sqlmodel import delete, select

logger = logging.getLogger("acex.observability.agents")

REDACTED = "«redacted»"


@dataclass
class _AgentScope:
    explicit: list[int]
    rules: list[TelemetryAgentMatchRule]
    rule_matched: set[int]

    @property
    def resolved(self) -> list[int]:
        return sorted(set(self.explicit) | self.rule_matched)

    def source(self, node_id: int) -> str:
        in_explicit = node_id in self.explicit
        in_rules = node_id in self.rule_matched
        return "both" if in_explicit and in_rules else "explicit" if in_explicit else "rule"


def _utc_now_naive() -> str:
    # Naive UTC ISO string (no offset) — the frontend appends "Z" when parsing.
    return datetime.now(UTC).replace(tzinfo=None).isoformat()


def _mask(value: str | None, reveal: bool) -> str | None:
    """Replace a set secret with a placeholder unless `reveal` is True."""
    return value if reveal or not value else REDACTED


class TelemetryAgentManager:
    def __init__(self, db_manager, telemetry_registry=None, influxdb_settings=None):
        self.db = db_manager
        self.telemetry_registry = telemetry_registry
        self.influxdb_settings = influxdb_settings

    def _bump_revision(self, session, agent_id: int):
        agent = session.get(TelemetryAgent, agent_id)
        if agent:
            agent.config_revision = (agent.config_revision or 0) + 1

    def agents_covering_nodes(self, node_ids: Iterable[int]) -> set[int]:
        """IDs of agents covering any of `node_ids`, via explicit link or
        matching rule. Rule resolution joins on Node/LogicalNode/Asset, so
        the result reflects the current DB state."""
        wanted = set(node_ids)
        if not wanted:
            return set()
        session = next(self.db.get_session())
        try:
            affected: set[int] = set(
                session.exec(
                    select(TelemetryAgentNodeLink.telemetry_agent_id).where(TelemetryAgentNodeLink.node_id.in_(wanted))
                ).all()
            )

            rules_by_agent: dict[int, list[TelemetryAgentMatchRule]] = {}
            for r in session.exec(select(TelemetryAgentMatchRule)).all():
                rules_by_agent.setdefault(r.telemetry_agent_id, []).append(r)
            for agent_id, agent_rules in rules_by_agent.items():
                if agent_id in affected:
                    continue
                if wanted & self._resolve_rule_nodes(session, agent_rules):
                    affected.add(agent_id)
            return affected
        finally:
            session.close()

    def bump_revisions(self, agent_ids: Iterable[int]) -> None:
        agent_ids = set(agent_ids)
        if not agent_ids:
            return
        session = next(self.db.get_session())
        try:
            for agent_id in agent_ids:
                self._bump_revision(session, agent_id)
            session.commit()
        finally:
            session.close()

    def bump_revisions_for_node(self, node_id: int) -> None:
        """Bump config_revision on every agent that covers `node_id`. Call
        AFTER node create and BEFORE node delete."""
        self.bump_revisions(self.agents_covering_nodes([node_id]))

    @contextmanager
    def bumping_revisions_for_nodes(self, node_ids: Iterable[int]) -> Iterator[None]:
        """Wrap a change to node attributes that rules match on (site, role,
        status, …). Agents covering the nodes before *or* after the change are
        bumped — so an agent that loses a node learns about it too. Nothing is
        bumped if the wrapped block raises."""
        node_ids = set(node_ids)
        before = self.agents_covering_nodes(node_ids)
        yield
        self.bump_revisions(before | self.agents_covering_nodes(node_ids))

    def _resolve_rule_nodes(self, session, rules: list[TelemetryAgentMatchRule]) -> set[int]:
        """Resolve node IDs matching any of the given rules."""
        if not rules:
            return set()

        matched_ids = set()
        for rule in rules:
            query = select(Node.id)

            # Join LogicalNode for site/role/region filtering
            needs_ln = any([rule.site, rule.role, rule.region])
            if needs_ln:
                query = query.join(LogicalNode, Node.logical_node_id == LogicalNode.id)
                if rule.site:
                    query = query.where(LogicalNode.site.ilike(f"{rule.site}%"))
                if rule.role:
                    query = query.where(LogicalNode.role.ilike(f"{rule.role}%"))
                if rule.region:
                    site_names = session.exec(
                        select(SiteRegionAssignment.site_name).where(SiteRegionAssignment.region_name == rule.region)
                    ).all()
                    if site_names:
                        query = query.where(LogicalNode.site.in_(site_names))
                    else:
                        continue

            # Join Asset for vendor/os filtering
            needs_asset = any([rule.vendor, rule.os])
            if needs_asset:
                query = query.join(Asset, Node.asset_ref_id == Asset.id)
                if rule.vendor:
                    query = query.where(Asset.vendor.ilike(f"{rule.vendor}%"))
                if rule.os:
                    query = query.where(Asset.os.ilike(f"{rule.os}%"))

            # Status filter directly on Node
            if rule.status:
                query = query.where(Node.status == rule.status)

            matched_ids |= set(session.exec(query).all())

        return matched_ids

    def _agent_capabilities(self, session, agent_id: int) -> list[TelemetryCapability]:
        return list(
            session.exec(
                select(TelemetryAgentCapabilityLink.capability).where(
                    TelemetryAgentCapabilityLink.telemetry_agent_id == agent_id
                )
            ).all()
        )

    def _explicit_node_ids(self, session, agent_id: int) -> list[int]:
        return list(
            session.exec(
                select(TelemetryAgentNodeLink.node_id).where(TelemetryAgentNodeLink.telemetry_agent_id == agent_id)
            ).all()
        )

    def _agent_rules(self, session, agent_id: int) -> list[TelemetryAgentMatchRule]:
        return list(
            session.exec(
                select(TelemetryAgentMatchRule).where(TelemetryAgentMatchRule.telemetry_agent_id == agent_id)
            ).all()
        )

    def _agent_scope(self, session, agent_id: int) -> _AgentScope:
        """Single source of truth for which nodes an agent covers:
        explicit links ∪ rule matches. Used by both the API response and
        config rendering so `resolved_nodes` always equals the rendered scope.
        """
        explicit = self._explicit_node_ids(session, agent_id)
        rules = self._agent_rules(session, agent_id)
        return _AgentScope(explicit, rules, self._resolve_rule_nodes(session, rules))

    def _node_hostnames(self, session, node_ids: list[int]) -> dict[int, str]:
        if not node_ids:
            return {}
        rows = session.exec(
            select(Node.id, LogicalNode.hostname)
            .join(LogicalNode, Node.logical_node_id == LogicalNode.id)
            .where(Node.id.in_(node_ids))
        ).all()
        return dict(rows)

    def _agent_components(self, node_ids: list[int], capabilities: list[TelemetryCapability]) -> AgentComponents:
        if self.telemetry_registry is None:
            return AgentComponents()
        return self.telemetry_registry.for_telegraf_agent(node_ids=node_ids, capabilities=capabilities)

    def _get_agent_response(
        self, session, agent: TelemetryAgent, scope: _AgentScope | None = None
    ) -> TelemetryAgentResponse:
        capabilities = self._agent_capabilities(session, agent.id)
        scope = scope or self._agent_scope(session, agent.id)
        explicit_node_ids = scope.explicit
        rules = scope.rules
        resolved = scope.resolved

        return TelemetryAgentResponse(
            id=agent.id,
            config_revision=agent.config_revision or 0,
            last_config_poll=agent.last_config_poll,
            acked_revision=agent.acked_revision or 0,
            acked_at=agent.acked_at,
            name=agent.name,
            description=agent.description,
            snmp_version=agent.snmp_version,
            snmp_trap_port=agent.snmp_trap_port,
            syslog_port=agent.syslog_port,
            snmpv3_sec_level=agent.snmpv3_sec_level,
            snmpv3_sec_name=agent.snmpv3_sec_name,
            snmpv2c_credential_id=agent.snmpv2c_credential_id,
            snmpv3_credential_id=agent.snmpv3_credential_id,
            capabilities=capabilities,
            nodes=explicit_node_ids,
            rules=[
                TelemetryAgentMatchRuleResponse(
                    id=r.id,
                    site=r.site,
                    vendor=r.vendor,
                    os=r.os,
                    status=r.status,
                    role=r.role,
                )
                for r in rules
            ],
            resolved_nodes=resolved,
        )

    def create(self, payload: TelemetryAgentCreate) -> TelemetryAgentResponse:
        session = next(self.db.get_session())
        try:
            agent = TelemetryAgent(**payload.model_dump(exclude={"capabilities"}, exclude_unset=True))
            session.add(agent)
            session.flush()

            for cap in payload.capabilities:
                link = TelemetryAgentCapabilityLink(telemetry_agent_id=agent.id, capability=cap)
                session.add(link)

            session.commit()
            session.refresh(agent)
            return self._get_agent_response(session, agent)
        finally:
            session.close()

    def query(
        self,
        name: str | None = None,
        capability: TelemetryCapability | None = None,
        node_id: int | None = None,
    ) -> list[TelemetryAgentResponse]:
        session = next(self.db.get_session())
        try:
            query = select(TelemetryAgent)

            if name is not None:
                query = query.where(TelemetryAgent.name.ilike(f"{name}%"))

            if capability is not None:
                query = query.join(TelemetryAgentCapabilityLink).where(
                    TelemetryAgentCapabilityLink.capability == capability
                )

            if node_id is not None:
                query = query.join(TelemetryAgentNodeLink).where(TelemetryAgentNodeLink.node_id == node_id)

            agents = session.exec(query).all()
            return [self._get_agent_response(session, agent) for agent in agents]
        finally:
            session.close()

    def get(self, id: int, include_coverage: bool = False) -> TelemetryAgentResponse:
        """Single agent. `include_coverage=true` adds `node_coverage`, which runs
        the telemetry providers (DB queries, per-node credential lookups) — the
        UI opts in; telemetry agents polling for `config_revision` do not."""
        session = next(self.db.get_session())
        try:
            agent = session.get(TelemetryAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="TelemetryAgent not found")
            scope = self._agent_scope(session, id)
            response = self._get_agent_response(session, agent, scope)
            hostnames = self._node_hostnames(session, scope.resolved) if include_coverage else {}
        finally:
            session.close()

        if not include_coverage:
            return response
        coverage = self._agent_components(scope.resolved, response.capabilities).coverage(scope.resolved)
        response.node_coverage = [
            NodeCoverage(
                node_id=node_id,
                hostname=hostnames.get(node_id),
                source=scope.source(node_id),
                capabilities=coverage[node_id],
            )
            for node_id in scope.resolved
        ]
        return response

    def update(self, id: int, payload: TelemetryAgentUpdate) -> TelemetryAgentResponse:
        session = next(self.db.get_session())
        try:
            agent = session.get(TelemetryAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="TelemetryAgent not found")

            if payload.name is not None:
                agent.name = payload.name
            if payload.description is not None:
                agent.description = payload.description

            for field in (
                "snmp_version",
                "snmp_trap_port",
                "syslog_port",
                "snmpv3_sec_level",
                "snmpv3_sec_name",
                "snmpv2c_credential_id",
                "snmpv3_credential_id",
            ):
                value = getattr(payload, field)
                if value is not None:
                    setattr(agent, field, value)

            if payload.capabilities is not None:
                session.exec(
                    delete(TelemetryAgentCapabilityLink).where(TelemetryAgentCapabilityLink.telemetry_agent_id == id)
                )
                for cap in payload.capabilities:
                    link = TelemetryAgentCapabilityLink(telemetry_agent_id=id, capability=cap)
                    session.add(link)

            self._bump_revision(session, id)
            session.commit()
            session.refresh(agent)
            return self._get_agent_response(session, agent)
        finally:
            session.close()

    def delete(self, id: int) -> None:
        session = next(self.db.get_session())
        try:
            agent = session.get(TelemetryAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="TelemetryAgent not found")

            session.exec(
                delete(TelemetryAgentCapabilityLink).where(TelemetryAgentCapabilityLink.telemetry_agent_id == id)
            )
            session.exec(delete(TelemetryAgentNodeLink).where(TelemetryAgentNodeLink.telemetry_agent_id == id))
            session.exec(delete(TelemetryAgentMatchRule).where(TelemetryAgentMatchRule.telemetry_agent_id == id))

            session.delete(agent)
            session.commit()
        finally:
            session.close()

    # --- Node mapping ---

    def add_node(self, id: int, node_id: int) -> None:
        session = next(self.db.get_session())
        try:
            agent = session.get(TelemetryAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="TelemetryAgent not found")

            node = session.get(Node, node_id)
            if not node:
                raise HTTPException(status_code=404, detail="Node not found")

            existing = session.exec(
                select(TelemetryAgentNodeLink).where(
                    TelemetryAgentNodeLink.telemetry_agent_id == id,
                    TelemetryAgentNodeLink.node_id == node_id,
                )
            ).first()
            if existing:
                raise HTTPException(status_code=409, detail="Node already assigned to this telemetry agent")

            link = TelemetryAgentNodeLink(telemetry_agent_id=id, node_id=node_id)
            session.add(link)
            self._bump_revision(session, id)
            session.commit()
        finally:
            session.close()

    def remove_node(self, id: int, node_id: int) -> None:
        session = next(self.db.get_session())
        try:
            link = session.exec(
                select(TelemetryAgentNodeLink).where(
                    TelemetryAgentNodeLink.telemetry_agent_id == id,
                    TelemetryAgentNodeLink.node_id == node_id,
                )
            ).first()
            if not link:
                raise HTTPException(status_code=404, detail="Node not assigned to this telemetry agent")

            session.delete(link)
            self._bump_revision(session, id)
            session.commit()
        finally:
            session.close()

    def set_nodes(self, id: int, payload: AgentNodeSet) -> AgentNodeSetResult:
        """Declaratively set the agent's explicit nodes (see `AgentNodeSet`)."""
        session = next(self.db.get_session())
        try:
            return set_agent_nodes(
                session,
                agent_model=TelemetryAgent,
                link_model=TelemetryAgentNodeLink,
                agent_fk="telemetry_agent_id",
                agent_id=id,
                node_ids=payload.node_ids,
                expected_revision=payload.expected_revision,
            )
        finally:
            session.close()

    # --- Match rules ---

    def add_rule(self, id: int, payload: TelemetryAgentMatchRuleCreate) -> TelemetryAgentMatchRuleResponse:
        session = next(self.db.get_session())
        try:
            agent = session.get(TelemetryAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="TelemetryAgent not found")

            rule = TelemetryAgentMatchRule(
                telemetry_agent_id=id,
                site=payload.site,
                vendor=payload.vendor,
                os=payload.os,
                status=payload.status,
                role=payload.role,
            )
            session.add(rule)
            self._bump_revision(session, id)
            session.commit()
            session.refresh(rule)
            return TelemetryAgentMatchRuleResponse(
                id=rule.id,
                site=rule.site,
                vendor=rule.vendor,
                os=rule.os,
                status=rule.status,
                role=rule.role,
            )
        finally:
            session.close()

    def remove_rule(self, id: int, rule_id: int) -> None:
        session = next(self.db.get_session())
        try:
            rule = session.exec(
                select(TelemetryAgentMatchRule).where(
                    TelemetryAgentMatchRule.id == rule_id,
                    TelemetryAgentMatchRule.telemetry_agent_id == id,
                )
            ).first()
            if not rule:
                raise HTTPException(status_code=404, detail="Rule not found")

            session.delete(rule)
            self._bump_revision(session, id)
            session.commit()
        finally:
            session.close()

    # --- Ack ---

    def ack(self, id: int, payload: TelemetryAgentAck) -> AckResult:
        session = next(self.db.get_session())
        try:
            agent = session.get(TelemetryAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="TelemetryAgent not found")
            agent.acked_revision = payload.config_revision
            agent.acked_at = _utc_now_naive()
            session.commit()
            return AckResult(
                id=agent.id,
                acked_revision=agent.acked_revision,
                acked_at=agent.acked_at,
            )
        finally:
            session.close()

    # --- Config generation ---

    def get_config(self, id: int, reveal_secrets: bool = False) -> str:
        """Render this agent's telegraf config.

        Secrets (InfluxDB token/password, SNMP trap community/auth/priv
        passwords) are masked as "«redacted»" unless `reveal_secrets` is
        True. The telemetry-agent sidecar always passes `reveal_secrets=True`
        to get a working config; this default-masked view is for humans
        (e.g. the frontend's "View config" link).
        """
        # 1. Read the agent's intent; the session is closed before providers
        #    run, since they (and credential lookups) open their own.
        session = next(self.db.get_session())
        try:
            agent = session.get(TelemetryAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="TelemetryAgent not found")
            capabilities = self._agent_capabilities(session, id)
            node_ids = self._agent_scope(session, id).resolved
        finally:
            session.close()

        # 2. Build components scoped to the agent's nodes and capabilities.
        scoped = self._agent_components(node_ids, capabilities)
        for s in scoped.skipped:
            logger.warning(
                "telemetry agent %s: node %s not rendered for %s (%s)%s",
                id,
                s.node_id,
                s.capability or "unknown capability",
                s.reason,
                f": {s.detail}" if s.detail else "",
            )

        # 3. Render. Agent-level errors (e.g. a misconfigured trap credential) still raise.
        config = self._render_telegraf_config(agent, capabilities, scoped.components, reveal_secrets)

        # 4. Record the poll only once a valid config has been produced.
        self._touch_last_config_poll(id)
        return config

    def _touch_last_config_poll(self, id: int) -> None:
        session = next(self.db.get_session())
        try:
            agent = session.get(TelemetryAgent, id)
            if agent:
                agent.last_config_poll = _utc_now_naive()
                session.commit()
        finally:
            session.close()

    def _render_telegraf_config(
        self,
        agent: TelemetryAgent,
        capabilities: builtins.list[TelemetryCapability],
        components: builtins.list[TelemetryComponent],
        reveal_secrets: bool = False,
    ) -> str:
        from acex.observability.renderers import (
            render_inputs,
            render_snmp_trap_input,
            render_syslog_input,
        )

        lines = []

        lines.append("# Telegraf configuration")
        lines.append(f"# Generated for telemetry agent: {agent.name}")
        lines.append("")
        lines.append("[agent]")
        lines.append('  hostname = ""')
        lines.append('  interval = "60s"')
        lines.append('  flush_interval = "10s"')
        lines.append("")

        has_inputs = False
        inputs_toml = render_inputs(components)
        if inputs_toml.strip():
            lines.append(inputs_toml)
            has_inputs = True

        # Service inputs — agent-scoped listeners, not registry-driven.
        cap_set = set(capabilities)

        if TelemetryCapability.snmp_trap in cap_set:
            version = agent.snmp_version.value if agent.snmp_version else "2c"
            port = agent.snmp_trap_port or 162

            # Receiver secrets come from mapped Credentials.
            community = None
            if agent.snmpv2c_credential_id is not None:
                community = self._get_credential_fields(
                    agent.snmpv2c_credential_id, expected_type="snmp_community"
                ).get("community")

            v3: dict = {}
            if agent.snmpv3_credential_id is not None:
                f = self._get_credential_fields(agent.snmpv3_credential_id, expected_type="snmpv3")
                v3 = {
                    "auth_protocol": f.get("auth_protocol"),
                    "auth_password": _mask(f.get("auth_password"), reveal_secrets),
                    "priv_protocol": f.get("priv_protocol"),
                    "priv_password": _mask(f.get("priv_password"), reveal_secrets),
                }
                # Credential username wins; otherwise fall back to inline sec_name.
                v3["sec_name"] = f.get("username") or agent.snmpv3_sec_name
            else:
                # No credential — inline sec_name (only meaningful with noAuthNoPriv).
                v3["sec_name"] = agent.snmpv3_sec_name

            lines.append(
                render_snmp_trap_input(
                    service_address=f"udp://:{port}",
                    version=version,
                    community=_mask(community, reveal_secrets),
                    sec_level=agent.snmpv3_sec_level.value if agent.snmpv3_sec_level else None,
                    **v3,
                )
            )
            has_inputs = True

        if TelemetryCapability.syslog_rfc5424 in cap_set:
            port = agent.syslog_port or 514
            lines.append(render_syslog_input(server=f"udp://:{port}"))
            has_inputs = True

        # Telegraf refuses to start without any input. An agent whose nodes are
        # all skipped (e.g. no management IPs yet) and that has no listeners
        # would otherwise crash-loop; fall back to Telegraf's own metrics.
        if not has_inputs:
            lines.append("[[inputs.internal]]")
            lines.append("")

        # Backend-default outputs (set in app.py via set_influxdb / add_influxdb),
        # applied to every agent.
        if self.influxdb_settings is not None:
            for default in self.influxdb_settings.default_outputs:
                lines.extend(self._render_output_block(default, reveal_secrets))

        return "\n".join(lines)

    def _get_credential_fields(self, credential_id: int, expected_type: str) -> dict:
        """Resolve a mapped credential to its decrypted fields.

        The credential must be of `expected_type`; anything else is a
        configuration error and surfaces as a 400 in the config endpoint.
        """
        cred_mgr = getattr(self.telemetry_registry, "credential_manager", None)
        if cred_mgr is None:
            raise HTTPException(
                status_code=400,
                detail=f"Agent references credential {credential_id} but no credential manager is configured",
            )
        secret = cred_mgr.get_secret(credential_id)
        if secret.credential_type != expected_type:
            raise HTTPException(
                status_code=400,
                detail=f"Credential {credential_id} is of type '{secret.credential_type}', expected '{expected_type}'",
            )
        return secret.fields

    def _render_output_block(self, dest, reveal_secrets: bool = False) -> builtins.list[str]:
        """Render one [[outputs.X]] block for a backend-default InfluxDBOutput."""
        version = dest.version
        url = dest.url
        token = _mask(dest.token, reveal_secrets)
        organization = dest.organization
        bucket = dest.bucket
        database = dest.database
        username = dest.username
        password = _mask(dest.password, reveal_secrets)
        content_encoding = dest.content_encoding

        lines: list[str] = []
        if version == InfluxDBVersion.v3:
            # InfluxDB v3 (IOx / Cloud Dedicated / Enterprise) — native plugin.
            # v3 went back to "database" terminology; "organization" remains optional.
            lines.append("[[outputs.influxdb_v3]]")
            lines.append(f'  urls = ["{url}"]')
            if token:
                lines.append(f'  token = "{token}"')
            if organization:
                lines.append(f'  organization = "{organization}"')
            if database:
                lines.append(f'  database = "{database}"')
        elif version == InfluxDBVersion.v2:
            lines.append("[[outputs.influxdb_v2]]")
            lines.append(f'  urls = ["{url}"]')
            if token:
                lines.append(f'  token = "{token}"')
            if organization:
                lines.append(f'  organization = "{organization}"')
            if bucket:
                lines.append(f'  bucket = "{bucket}"')
        else:
            lines.append("[[outputs.influxdb]]")
            lines.append(f'  urls = ["{url}"]')
            if database:
                lines.append(f'  database = "{database}"')
            if username:
                lines.append(f'  username = "{username}"')
            if password:
                lines.append(f'  password = "{password}"')

        if content_encoding:
            lines.append(f'  content_encoding = "{content_encoding}"')
        lines.append("")
        return lines
