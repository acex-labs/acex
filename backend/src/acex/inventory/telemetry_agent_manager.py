from typing import Optional, List, Set

from fastapi import HTTPException
from sqlalchemy import or_

from acex.models.telemetry_agent import (
    TelemetryAgent,
    TelemetryAgentCreate,
    TelemetryAgentUpdate,
    TelemetryAgentResponse,
    TelemetryAgentNodeLink,
    TelemetryAgentCapabilityLink,
    TelemetryAgentMatchRule,
    TelemetryAgentMatchRuleCreate,
    TelemetryAgentMatchRuleResponse,
    TelemetryCapability,
    OutputDestination,
    OutputDestinationCreate,
    OutputDestinationUpdate,
    OutputDestinationResponse,
    InfluxDBVersion,
)
from acex.models.node import Node
from acex.models.asset import Asset, AssetCluster
from acex.models.management_connections import ManagementConnection
from acex.models.logical_node import LogicalNode


class TelemetryAgentManager:

    def __init__(self, db_manager):
        self.db = db_manager

    def _bump_revision(self, session, agent_id: int):
        agent = session.get(TelemetryAgent, agent_id)
        if agent:
            agent.config_revision = (agent.config_revision or 0) + 1

    def _resolve_rule_nodes(self, session, rules: List[TelemetryAgentMatchRule]) -> Set[int]:
        """Resolve node IDs matching any of the given rules."""
        if not rules:
            return set()

        matched_ids = set()
        for rule in rules:
            query = session.query(Node.id)

            # Join LogicalNode for site/role/hostname filtering
            needs_ln = any([rule.site, rule.role])
            if needs_ln:
                query = query.join(LogicalNode, Node.logical_node_id == LogicalNode.id)
                if rule.site:
                    query = query.filter(LogicalNode.site.ilike(f"{rule.site}%"))
                if rule.role:
                    query = query.filter(LogicalNode.role.ilike(f"{rule.role}%"))

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
            session.query(TelemetryAgentNodeLink)
            .filter(TelemetryAgentNodeLink.telemetry_agent_id == agent.id)
            .all()
        )
        cap_links = (
            session.query(TelemetryAgentCapabilityLink)
            .filter(TelemetryAgentCapabilityLink.telemetry_agent_id == agent.id)
            .all()
        )
        rules = (
            session.query(TelemetryAgentMatchRule)
            .filter(TelemetryAgentMatchRule.telemetry_agent_id == agent.id)
            .all()
        )

        outputs = (
            session.query(OutputDestination)
            .filter(OutputDestination.telemetry_agent_id == agent.id)
            .all()
        )

        explicit_node_ids = [link.node_id for link in node_links]
        rule_matched_ids = self._resolve_rule_nodes(session, rules)
        resolved = sorted(set(explicit_node_ids) | rule_matched_ids)

        return TelemetryAgentResponse(
            id=agent.id,
            config_revision=agent.config_revision or 0,
            name=agent.name,
            description=agent.description,
            capabilities=[link.capability for link in cap_links],
            nodes=explicit_node_ids,
            rules=[
                TelemetryAgentMatchRuleResponse(
                    id=r.id, site=r.site, vendor=r.vendor,
                    os=r.os, status=r.status, role=r.role,
                )
                for r in rules
            ],
            resolved_nodes=resolved,
            outputs=[
                OutputDestinationResponse(
                    id=o.id, influxdb_version=o.influxdb_version, url=o.url,
                    token=o.token, organization=o.organization, bucket=o.bucket,
                    database=o.database, username=o.username, password=o.password,
                )
                for o in outputs
            ],
        )

    def create(self, payload: TelemetryAgentCreate) -> TelemetryAgentResponse:
        session = next(self.db.get_session())
        try:
            agent = TelemetryAgent(name=payload.name, description=payload.description)
            session.add(agent)
            session.flush()

            for cap in payload.capabilities:
                link = TelemetryAgentCapabilityLink(
                    telemetry_agent_id=agent.id, capability=cap
                )
                session.add(link)

            session.commit()
            session.refresh(agent)
            return self._get_agent_response(session, agent)
        finally:
            session.close()

    def list(
        self,
        name: Optional[str] = None,
        capability: Optional[TelemetryCapability] = None,
        node_id: Optional[int] = None,
    ) -> List[TelemetryAgentResponse]:
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
                query = query.join(TelemetryAgentNodeLink).filter(
                    TelemetryAgentNodeLink.node_id == node_id
                )

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

            if payload.capabilities is not None:
                session.query(TelemetryAgentCapabilityLink).filter(
                    TelemetryAgentCapabilityLink.telemetry_agent_id == id
                ).delete()
                for cap in payload.capabilities:
                    link = TelemetryAgentCapabilityLink(
                        telemetry_agent_id=id, capability=cap
                    )
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
            session.query(TelemetryAgentNodeLink).filter(
                TelemetryAgentNodeLink.telemetry_agent_id == id
            ).delete()
            session.query(TelemetryAgentMatchRule).filter(
                TelemetryAgentMatchRule.telemetry_agent_id == id
            ).delete()
            session.query(OutputDestination).filter(
                OutputDestination.telemetry_agent_id == id
            ).delete()

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
                id=rule.id, site=rule.site, vendor=rule.vendor,
                os=rule.os, status=rule.status, role=rule.role,
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

    # --- Output destinations ---

    def add_output(self, id: int, payload: OutputDestinationCreate) -> OutputDestinationResponse:
        session = next(self.db.get_session())
        try:
            agent = session.get(TelemetryAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="TelemetryAgent not found")

            dest = OutputDestination(
                telemetry_agent_id=id,
                influxdb_version=payload.influxdb_version,
                url=payload.url,
                token=payload.token,
                organization=payload.organization,
                bucket=payload.bucket,
                database=payload.database,
                username=payload.username,
                password=payload.password,
            )
            session.add(dest)
            self._bump_revision(session, id)
            session.commit()
            session.refresh(dest)
            return OutputDestinationResponse(
                id=dest.id, influxdb_version=dest.influxdb_version, url=dest.url,
                token=dest.token, organization=dest.organization, bucket=dest.bucket,
                database=dest.database, username=dest.username, password=dest.password,
            )
        finally:
            session.close()

    def update_output(self, id: int, output_id: int, payload: OutputDestinationUpdate) -> OutputDestinationResponse:
        session = next(self.db.get_session())
        try:
            dest = (
                session.query(OutputDestination)
                .filter(OutputDestination.id == output_id, OutputDestination.telemetry_agent_id == id)
                .first()
            )
            if not dest:
                raise HTTPException(status_code=404, detail="Output destination not found")

            for field in ['influxdb_version', 'url', 'token', 'organization', 'bucket', 'database', 'username', 'password']:
                value = getattr(payload, field)
                if value is not None:
                    setattr(dest, field, value)

            self._bump_revision(session, id)
            session.commit()
            session.refresh(dest)
            return OutputDestinationResponse(
                id=dest.id, influxdb_version=dest.influxdb_version, url=dest.url,
                token=dest.token, organization=dest.organization, bucket=dest.bucket,
                database=dest.database, username=dest.username, password=dest.password,
            )
        finally:
            session.close()

    def remove_output(self, id: int, output_id: int) -> None:
        session = next(self.db.get_session())
        try:
            dest = (
                session.query(OutputDestination)
                .filter(OutputDestination.id == output_id, OutputDestination.telemetry_agent_id == id)
                .first()
            )
            if not dest:
                raise HTTPException(status_code=404, detail="Output destination not found")

            session.delete(dest)
            self._bump_revision(session, id)
            session.commit()
        finally:
            session.close()

    # --- Config generation ---

    def get_config(self, id: int) -> str:
        session = next(self.db.get_session())
        try:
            agent = session.get(TelemetryAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="TelemetryAgent not found")

            # Hämta capabilities
            cap_links = (
                session.query(TelemetryAgentCapabilityLink)
                .filter(TelemetryAgentCapabilityLink.telemetry_agent_id == id)
                .all()
            )
            capabilities = [link.capability for link in cap_links]

            # Hämta explicita noder
            node_links = (
                session.query(TelemetryAgentNodeLink)
                .filter(TelemetryAgentNodeLink.telemetry_agent_id == id)
                .all()
            )
            explicit_ids = {link.node_id for link in node_links}

            # Hämta regelmatchade noder
            rules = (
                session.query(TelemetryAgentMatchRule)
                .filter(TelemetryAgentMatchRule.telemetry_agent_id == id)
                .all()
            )
            rule_ids = self._resolve_rule_nodes(session, rules)

            # Union
            all_node_ids = sorted(explicit_ids | rule_ids)

            # Hämta noder
            nodes = session.query(Node).filter(Node.id.in_(all_node_ids)).all() if all_node_ids else []

            # Hämta management connections för nodernas IP-adresser
            mgmt_connections = (
                session.query(ManagementConnection)
                .filter(ManagementConnection.node_id.in_(all_node_ids))
                .all()
            ) if all_node_ids else []

            # Bygg lookup: node_id -> target_ip (primär connection)
            node_ip_map = {}
            for conn in mgmt_connections:
                if conn.node_id not in node_ip_map or conn.primary:
                    node_ip_map[conn.node_id] = conn.target_ip

            # Hämta hostnames via logical_node
            ln_ids = [n.logical_node_id for n in nodes]
            logical_nodes = (
                session.query(LogicalNode).filter(LogicalNode.id.in_(ln_ids)).all()
            ) if ln_ids else []
            ln_map = {ln.id: ln.hostname for ln in logical_nodes}

            # Hämta output destinations
            outputs = (
                session.query(OutputDestination)
                .filter(OutputDestination.telemetry_agent_id == id)
                .all()
            )

            return self._render_telegraf_config(agent, capabilities, nodes, node_ip_map, ln_map, outputs)
        finally:
            session.close()

    def _render_telegraf_config(
        self,
        agent: TelemetryAgent,
        capabilities: List[TelemetryCapability],
        nodes: List[Node],
        node_ip_map: dict,
        ln_map: dict,
        outputs: List[OutputDestination],
    ) -> str:
        lines = []

        # Agent section
        lines.append("# Telegraf configuration")
        lines.append(f"# Generated for telemetry agent: {agent.name}")
        lines.append("")
        lines.append("[agent]")
        lines.append('  hostname = ""')
        lines.append("  interval = \"60s\"")
        lines.append("  flush_interval = \"10s\"")
        lines.append("")

        # SNMP inputs
        if TelemetryCapability.snmp in capabilities:
            for node in nodes:
                ip = node_ip_map.get(node.id)
                hostname = ln_map.get(node.logical_node_id, f"node-{node.id}")
                if not ip:
                    continue

                lines.append("[[inputs.snmp]]")
                lines.append(f'  agents = ["udp://{ip}:161"]')
                lines.append(f'  name = "{hostname}"')
                lines.append("  version = 2")
                lines.append('  community = "public"')
                lines.append("")
                lines.append("  [[inputs.snmp.field]]")
                lines.append('    oid = "RFC1213-MIB::sysUpTime.0"')
                lines.append('    name = "uptime"')
                lines.append("")
                lines.append("  [[inputs.snmp.field]]")
                lines.append('    oid = "RFC1213-MIB::sysName.0"')
                lines.append('    name = "source"')
                lines.append("    is_tag = true")
                lines.append("")

        # Ping inputs
        if TelemetryCapability.icmp in capabilities:
            ping_urls = []
            for node in nodes:
                ip = node_ip_map.get(node.id)
                if ip:
                    ping_urls.append(f'    "{ip}"')

            if ping_urls:
                lines.append("[[inputs.ping]]")
                lines.append("  urls = [")
                lines.append(",\n".join(ping_urls))
                lines.append("  ]")
                lines.append("  count = 3")
                lines.append("  ping_interval = 1.0")
                lines.append("  timeout = 5.0")
                lines.append("")

        # Output destinations
        for dest in outputs:
            if dest.influxdb_version == InfluxDBVersion.v2:
                lines.append("[[outputs.influxdb_v2]]")
                lines.append(f'  urls = ["{dest.url}"]')
                if dest.token:
                    lines.append(f'  token = "{dest.token}"')
                if dest.organization:
                    lines.append(f'  organization = "{dest.organization}"')
                if dest.bucket:
                    lines.append(f'  bucket = "{dest.bucket}"')
                lines.append("")
            else:
                lines.append("[[outputs.influxdb]]")
                lines.append(f'  urls = ["{dest.url}"]')
                if dest.database:
                    lines.append(f'  database = "{dest.database}"')
                if dest.username:
                    lines.append(f'  username = "{dest.username}"')
                if dest.password:
                    lines.append(f'  password = "{dest.password}"')
                lines.append("")

        return "\n".join(lines)
