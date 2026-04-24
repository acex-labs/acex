from typing import Optional, List, Set
from datetime import datetime

from fastapi import HTTPException

from acex.models.config_agent import (
    ConfigAgent,
    ConfigAgentCreate,
    ConfigAgentUpdate,
    ConfigAgentResponse,
    ConfigAgentNodeLink,
    ConfigAgentMatchRule,
    ConfigAgentMatchRuleCreate,
    ConfigAgentMatchRuleResponse,
)
from acex.models.node import Node
from acex.models.asset import Asset
from acex.models.management_connections import ManagementConnection
from acex.models.logical_node import LogicalNode


class ConfigAgentManager:

    def __init__(self, db_manager):
        self.db = db_manager

    def _bump_revision(self, session, agent_id: int):
        agent = session.get(ConfigAgent, agent_id)
        if agent:
            agent.config_revision = (agent.config_revision or 0) + 1

    def _resolve_rule_nodes(self, session, rules: List[ConfigAgentMatchRule]) -> Set[int]:
        if not rules:
            return set()

        matched_ids = set()
        for rule in rules:
            query = session.query(Node.id)

            needs_ln = any([rule.site, rule.role])
            if needs_ln:
                query = query.join(LogicalNode, Node.logical_node_id == LogicalNode.id)
                if rule.site:
                    query = query.filter(LogicalNode.site.ilike(f"{rule.site}%"))
                if rule.role:
                    query = query.filter(LogicalNode.role.ilike(f"{rule.role}%"))

            needs_asset = any([rule.vendor, rule.os])
            if needs_asset:
                query = query.join(Asset, Node.asset_ref_id == Asset.id)
                if rule.vendor:
                    query = query.filter(Asset.vendor.ilike(f"{rule.vendor}%"))
                if rule.os:
                    query = query.filter(Asset.os.ilike(f"{rule.os}%"))

            if rule.status:
                query = query.filter(Node.status == rule.status)

            ids = {row[0] for row in query.all()}
            matched_ids |= ids

        return matched_ids

    def _get_agent_response(self, session, agent: ConfigAgent) -> ConfigAgentResponse:
        node_links = (
            session.query(ConfigAgentNodeLink)
            .filter(ConfigAgentNodeLink.config_agent_id == agent.id)
            .all()
        )
        rules = (
            session.query(ConfigAgentMatchRule)
            .filter(ConfigAgentMatchRule.config_agent_id == agent.id)
            .all()
        )

        explicit_node_ids = [link.node_id for link in node_links]
        rule_matched_ids = self._resolve_rule_nodes(session, rules)
        resolved = sorted(set(explicit_node_ids) | rule_matched_ids)

        return ConfigAgentResponse(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            interval_seconds=agent.interval_seconds,
            enabled=agent.enabled,
            config_revision=agent.config_revision or 0,
            last_manifest_poll=agent.last_manifest_poll,
            nodes=explicit_node_ids,
            rules=[
                ConfigAgentMatchRuleResponse(
                    id=r.id, site=r.site, vendor=r.vendor,
                    os=r.os, status=r.status, role=r.role,
                )
                for r in rules
            ],
            resolved_nodes=resolved,
        )

    # --- CRUD ---

    def create(self, payload: ConfigAgentCreate) -> ConfigAgentResponse:
        session = next(self.db.get_session())
        try:
            agent = ConfigAgent(
                name=payload.name,
                description=payload.description,
                interval_seconds=payload.interval_seconds,
                enabled=payload.enabled,
            )
            session.add(agent)
            session.commit()
            session.refresh(agent)
            return self._get_agent_response(session, agent)
        finally:
            session.close()

    def list(
        self,
        name: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> List[ConfigAgentResponse]:
        session = next(self.db.get_session())
        try:
            query = session.query(ConfigAgent)
            if name is not None:
                query = query.filter(ConfigAgent.name.ilike(f"{name}%"))
            if enabled is not None:
                query = query.filter(ConfigAgent.enabled == enabled)
            agents = query.all()
            return [self._get_agent_response(session, agent) for agent in agents]
        finally:
            session.close()

    def get(self, id: int) -> ConfigAgentResponse:
        session = next(self.db.get_session())
        try:
            agent = session.get(ConfigAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="ConfigAgent not found")
            return self._get_agent_response(session, agent)
        finally:
            session.close()

    def update(self, id: int, payload: ConfigAgentUpdate) -> ConfigAgentResponse:
        session = next(self.db.get_session())
        try:
            agent = session.get(ConfigAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="ConfigAgent not found")

            for field in ['name', 'description', 'interval_seconds', 'enabled']:
                value = getattr(payload, field)
                if value is not None:
                    setattr(agent, field, value)

            self._bump_revision(session, id)
            session.commit()
            session.refresh(agent)
            return self._get_agent_response(session, agent)
        finally:
            session.close()

    def delete(self, id: int) -> None:
        session = next(self.db.get_session())
        try:
            agent = session.get(ConfigAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="ConfigAgent not found")

            session.query(ConfigAgentNodeLink).filter(
                ConfigAgentNodeLink.config_agent_id == id
            ).delete()
            session.query(ConfigAgentMatchRule).filter(
                ConfigAgentMatchRule.config_agent_id == id
            ).delete()

            session.delete(agent)
            session.commit()
        finally:
            session.close()

    # --- Node mapping ---

    def add_node(self, id: int, node_id: int) -> None:
        session = next(self.db.get_session())
        try:
            agent = session.get(ConfigAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="ConfigAgent not found")

            node = session.get(Node, node_id)
            if not node:
                raise HTTPException(status_code=404, detail="Node not found")

            existing = (
                session.query(ConfigAgentNodeLink)
                .filter(
                    ConfigAgentNodeLink.config_agent_id == id,
                    ConfigAgentNodeLink.node_id == node_id,
                )
                .first()
            )
            if existing:
                raise HTTPException(status_code=409, detail="Node already assigned to this config agent")

            link = ConfigAgentNodeLink(config_agent_id=id, node_id=node_id)
            session.add(link)
            self._bump_revision(session, id)
            session.commit()
        finally:
            session.close()

    def remove_node(self, id: int, node_id: int) -> None:
        session = next(self.db.get_session())
        try:
            link = (
                session.query(ConfigAgentNodeLink)
                .filter(
                    ConfigAgentNodeLink.config_agent_id == id,
                    ConfigAgentNodeLink.node_id == node_id,
                )
                .first()
            )
            if not link:
                raise HTTPException(status_code=404, detail="Node not assigned to this config agent")

            session.delete(link)
            self._bump_revision(session, id)
            session.commit()
        finally:
            session.close()

    # --- Match rules ---

    def add_rule(self, id: int, payload: ConfigAgentMatchRuleCreate) -> ConfigAgentMatchRuleResponse:
        session = next(self.db.get_session())
        try:
            agent = session.get(ConfigAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="ConfigAgent not found")

            rule = ConfigAgentMatchRule(
                config_agent_id=id,
                site=payload.site, vendor=payload.vendor,
                os=payload.os, status=payload.status, role=payload.role,
            )
            session.add(rule)
            self._bump_revision(session, id)
            session.commit()
            session.refresh(rule)
            return ConfigAgentMatchRuleResponse(
                id=rule.id, site=rule.site, vendor=rule.vendor,
                os=rule.os, status=rule.status, role=rule.role,
            )
        finally:
            session.close()

    def remove_rule(self, id: int, rule_id: int) -> None:
        session = next(self.db.get_session())
        try:
            rule = (
                session.query(ConfigAgentMatchRule)
                .filter(
                    ConfigAgentMatchRule.id == rule_id,
                    ConfigAgentMatchRule.config_agent_id == id,
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

    # --- Manifest ---

    def get_manifest(self, id: int) -> dict:
        session = next(self.db.get_session())
        try:
            agent = session.get(ConfigAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="ConfigAgent not found")

            # Resolve nodes
            node_links = (
                session.query(ConfigAgentNodeLink)
                .filter(ConfigAgentNodeLink.config_agent_id == id)
                .all()
            )
            explicit_ids = {link.node_id for link in node_links}

            rules = (
                session.query(ConfigAgentMatchRule)
                .filter(ConfigAgentMatchRule.config_agent_id == id)
                .all()
            )
            rule_ids = self._resolve_rule_nodes(session, rules)
            all_node_ids = sorted(explicit_ids | rule_ids)

            nodes = session.query(Node).filter(Node.id.in_(all_node_ids)).all() if all_node_ids else []

            # Management connections
            mgmt_connections = (
                session.query(ManagementConnection)
                .filter(ManagementConnection.node_id.in_(all_node_ids))
                .all()
            ) if all_node_ids else []

            node_ip_map = {}
            node_conn_type_map = {}
            for conn in mgmt_connections:
                if conn.node_id not in node_ip_map or conn.primary:
                    node_ip_map[conn.node_id] = conn.target_ip
                    node_conn_type_map[conn.node_id] = conn.connection_type.value

            # Assets for NED lookup
            asset_ids = [n.asset_ref_id for n in nodes]
            assets = session.query(Asset).filter(Asset.id.in_(asset_ids)).all() if asset_ids else []
            asset_map = {a.id: a for a in assets}

            # Logical nodes for hostname
            ln_ids = [n.logical_node_id for n in nodes]
            logical_nodes = (
                session.query(LogicalNode).filter(LogicalNode.id.in_(ln_ids)).all()
            ) if ln_ids else []
            ln_map = {ln.id: ln.hostname for ln in logical_nodes}

            targets = []
            for node in nodes:
                asset = asset_map.get(node.asset_ref_id)
                targets.append({
                    "node_id": node.id,
                    "hostname": ln_map.get(node.logical_node_id),
                    "target_ip": node_ip_map.get(node.id),
                    "connection_type": node_conn_type_map.get(node.id),
                    "ned_id": asset.ned_id if asset else None,
                    "vendor": asset.vendor if asset else None,
                    "os": asset.os if asset else None,
                })

            # Update poll timestamp
            agent.last_manifest_poll = datetime.utcnow().isoformat()
            session.commit()

            return {
                "agent_id": agent.id,
                "name": agent.name,
                "config_revision": agent.config_revision or 0,
                "interval_seconds": agent.interval_seconds,
                "enabled": agent.enabled,
                "targets": targets,
            }
        finally:
            session.close()
