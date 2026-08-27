import builtins
from datetime import datetime

from acex.models.asset import Asset
from acex.models.logical_node import LogicalNode
from acex.models.management_connections import ManagementConnection
from acex.models.node import Node
from acex.models.regions import SiteRegionAssignment
from acex.observability.agents.models import (
    TelemetryAgent,
    TelemetryAgentCapabilityLink,
    TelemetryAgentMatchRule,
    TelemetryAgentNodeLink,
)
from acex.observability.capability import TelemetryCapability
from acex_devkit.models.agent_manifest import AckResult
from acex_devkit.models.telemetry_agent import (
    InfluxDBVersion,
    TelemetryAgentAck,
    TelemetryAgentCreate,
    TelemetryAgentMatchRuleCreate,
    TelemetryAgentMatchRuleResponse,
    TelemetryAgentResponse,
    TelemetryAgentUpdate,
)
from fastapi import HTTPException

REDACTED = "«redacted»"


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

    def bump_revisions_for_node(self, node_id: int) -> None:
        """Bump config_revision on every agent that covers `node_id`, via
        explicit link or matching rule. Call AFTER node create and BEFORE
        node delete — rule resolution joins on Node/LogicalNode/Asset.
        """
        session = next(self.db.get_session())
        try:
            affected: set[int] = {
                row[0]
                for row in (
                    session.query(TelemetryAgentNodeLink.telemetry_agent_id)
                    .filter(TelemetryAgentNodeLink.node_id == node_id)
                    .all()
                )
            }

            rules_by_agent: dict[int, list[TelemetryAgentMatchRule]] = {}
            for r in session.query(TelemetryAgentMatchRule).all():
                rules_by_agent.setdefault(r.telemetry_agent_id, []).append(r)
            for agent_id, agent_rules in rules_by_agent.items():
                if agent_id in affected:
                    continue
                if node_id in self._resolve_rule_nodes(session, agent_rules):
                    affected.add(agent_id)

            if not affected:
                return

            for agent_id in affected:
                self._bump_revision(session, agent_id)
            session.commit()
        finally:
            session.close()

    def _resolve_rule_nodes(self, session, rules: list[TelemetryAgentMatchRule]) -> set[int]:
        """Resolve node IDs matching any of the given rules."""
        if not rules:
            return set()

        matched_ids = set()
        for rule in rules:
            query = session.query(Node.id)

            # Join LogicalNode for site/role/region filtering
            needs_ln = any([rule.site, rule.role, rule.region])
            if needs_ln:
                query = query.join(LogicalNode, Node.logical_node_id == LogicalNode.id)
                if rule.site:
                    query = query.filter(LogicalNode.site.ilike(f"{rule.site}%"))
                if rule.role:
                    query = query.filter(LogicalNode.role.ilike(f"{rule.role}%"))
                if rule.region:
                    site_names = [
                        row[0]
                        for row in session.query(SiteRegionAssignment.site_name)
                        .filter(SiteRegionAssignment.region_name == rule.region)
                        .all()
                    ]
                    if site_names:
                        query = query.filter(LogicalNode.site.in_(site_names))
                    else:
                        continue

            # Join Asset for vendor/os filtering
            needs_asset = any([rule.vendor, rule.os])
            if needs_asset:
                query = query.join(Asset, Node.asset_ref_id == Asset.id)
                if rule.vendor:
                    query = query.filter(Asset.vendor.ilike(f"{rule.vendor}%"))
                if rule.os:
                    query = query.filter(Asset.os.ilike(f"{rule.os}%"))

            # Status filter directly on Node
            if rule.status:
                query = query.filter(Node.status == rule.status)

            ids = {row[0] for row in query.all()}
            matched_ids |= ids

        return matched_ids

    def _get_agent_response(self, session, agent: TelemetryAgent) -> TelemetryAgentResponse:
        node_links = (
            session.query(TelemetryAgentNodeLink).filter(TelemetryAgentNodeLink.telemetry_agent_id == agent.id).all()
        )
        cap_links = (
            session.query(TelemetryAgentCapabilityLink)
            .filter(TelemetryAgentCapabilityLink.telemetry_agent_id == agent.id)
            .all()
        )
        rules = (
            session.query(TelemetryAgentMatchRule).filter(TelemetryAgentMatchRule.telemetry_agent_id == agent.id).all()
        )

        explicit_node_ids = [link.node_id for link in node_links]
        rule_matched_ids = self._resolve_rule_nodes(session, rules)
        resolved = sorted(set(explicit_node_ids) | rule_matched_ids)

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
            capabilities=[link.capability for link in cap_links],
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
            query = session.query(TelemetryAgent)

            if name is not None:
                query = query.filter(TelemetryAgent.name.ilike(f"{name}%"))

            if capability is not None:
                query = query.join(TelemetryAgentCapabilityLink).filter(
                    TelemetryAgentCapabilityLink.capability == capability
                )

            if node_id is not None:
                query = query.join(TelemetryAgentNodeLink).filter(TelemetryAgentNodeLink.node_id == node_id)

            agents = query.all()
            return [self._get_agent_response(session, agent) for agent in agents]
        finally:
            session.close()

    def get(self, id: int) -> TelemetryAgentResponse:
        session = next(self.db.get_session())
        try:
            agent = session.get(TelemetryAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="TelemetryAgent not found")
            return self._get_agent_response(session, agent)
        finally:
            session.close()

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
                session.query(TelemetryAgentCapabilityLink).filter(
                    TelemetryAgentCapabilityLink.telemetry_agent_id == id
                ).delete()
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

            session.query(TelemetryAgentCapabilityLink).filter(
                TelemetryAgentCapabilityLink.telemetry_agent_id == id
            ).delete()
            session.query(TelemetryAgentNodeLink).filter(TelemetryAgentNodeLink.telemetry_agent_id == id).delete()
            session.query(TelemetryAgentMatchRule).filter(TelemetryAgentMatchRule.telemetry_agent_id == id).delete()

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

            existing = (
                session.query(TelemetryAgentNodeLink)
                .filter(
                    TelemetryAgentNodeLink.telemetry_agent_id == id,
                    TelemetryAgentNodeLink.node_id == node_id,
                )
                .first()
            )
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
            link = (
                session.query(TelemetryAgentNodeLink)
                .filter(
                    TelemetryAgentNodeLink.telemetry_agent_id == id,
                    TelemetryAgentNodeLink.node_id == node_id,
                )
                .first()
            )
            if not link:
                raise HTTPException(status_code=404, detail="Node not assigned to this telemetry agent")

            session.delete(link)
            self._bump_revision(session, id)
            session.commit()
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
            rule = (
                session.query(TelemetryAgentMatchRule)
                .filter(
                    TelemetryAgentMatchRule.id == rule_id,
                    TelemetryAgentMatchRule.telemetry_agent_id == id,
                )
                .first()
            )
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
            agent.acked_at = datetime.utcnow().isoformat()
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
        session = next(self.db.get_session())
        try:
            agent = session.get(TelemetryAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="TelemetryAgent not found")

            cap_links = (
                session.query(TelemetryAgentCapabilityLink)
                .filter(TelemetryAgentCapabilityLink.telemetry_agent_id == id)
                .all()
            )
            capabilities = [link.capability for link in cap_links]

            node_links = (
                session.query(TelemetryAgentNodeLink).filter(TelemetryAgentNodeLink.telemetry_agent_id == id).all()
            )
            explicit_ids = {link.node_id for link in node_links}

            rules = (
                session.query(TelemetryAgentMatchRule).filter(TelemetryAgentMatchRule.telemetry_agent_id == id).all()
            )
            rule_ids = self._resolve_rule_nodes(session, rules)

            all_node_ids = sorted(explicit_ids | rule_ids)

            nodes = session.query(Node).filter(Node.id.in_(all_node_ids)).all() if all_node_ids else []

            mgmt_connections = (
                (session.query(ManagementConnection).filter(ManagementConnection.node_id.in_(all_node_ids)).all())
                if all_node_ids
                else []
            )

            node_ip_map = {}
            for conn in mgmt_connections:
                if conn.node_id not in node_ip_map or conn.primary:
                    node_ip_map[conn.node_id] = conn.target_ip

            ln_ids = [n.logical_node_id for n in nodes]
            logical_nodes = (session.query(LogicalNode).filter(LogicalNode.id.in_(ln_ids)).all()) if ln_ids else []
            ln_map = {ln.id: ln.hostname for ln in logical_nodes}

            agent.last_config_poll = datetime.utcnow().isoformat()
            session.commit()

            return self._render_telegraf_config(agent, capabilities, nodes, node_ip_map, ln_map, reveal_secrets)
        finally:
            session.close()

    def _render_telegraf_config(
        self,
        agent: TelemetryAgent,
        capabilities: builtins.list[TelemetryCapability],
        nodes: builtins.list[Node],
        node_ip_map: dict,
        ln_map: dict,
        reveal_secrets: bool = False,
    ) -> str:
        lines = []

        lines.append("# Telegraf configuration")
        lines.append(f"# Generated for telemetry agent: {agent.name}")
        lines.append("")
        lines.append("[agent]")
        lines.append('  hostname = ""')
        lines.append('  interval = "60s"')
        lines.append('  flush_interval = "10s"')
        lines.append("")

        if self.telemetry_registry is not None:
            from acex.observability.renderers import render_inputs

            agent_node_ids = {n.id for n in nodes}
            components = self.telemetry_registry.for_telegraf_agent(
                node_ids=agent_node_ids,
                capabilities=set(capabilities),
            )
            inputs_toml = render_inputs(components)
            if inputs_toml.strip():
                lines.append(inputs_toml)

        # Service inputs — agent-scoped listeners, not registry-driven.
        cap_set = set(capabilities)
        from acex.observability.renderers import (
            render_snmp_trap_input,
            render_syslog_input,
        )

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

        if TelemetryCapability.syslog_rfc5424 in cap_set:
            port = agent.syslog_port or 514
            lines.append(render_syslog_input(server=f"udp://:{port}"))

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
