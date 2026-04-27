from typing import Optional, List, Set
from datetime import datetime

from fastapi import HTTPException

from acex.models.collection_agent import (
    CollectionAgent,
    CollectionAgentCreate,
    CollectionAgentUpdate,
    CollectionAgentResponse,
    CollectionAgentAck,
    CollectionAgentNodeLink,
    CollectionAgentMatchRule,
    CollectionAgentMatchRuleCreate,
    CollectionAgentMatchRuleResponse,
)
from acex.models.node import Node
from acex.models.asset import Asset
from acex.models.management_connections import ManagementConnection
from acex.models.logical_node import LogicalNode
from acex.models.credential import NodeCredential, Credential


class CollectionAgentManager:

    def __init__(self, db_manager):
        self.db = db_manager

    def _bump_revision(self, session, agent_id: int):
        agent = session.get(CollectionAgent, agent_id)
        if agent:
            agent.config_revision = (agent.config_revision or 0) + 1

    def _resolve_rule_nodes(self, session, rules: List[CollectionAgentMatchRule]) -> Set[int]:
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

    def _get_agent_response(self, session, agent: CollectionAgent) -> CollectionAgentResponse:
        node_links = (
            session.query(CollectionAgentNodeLink)
            .filter(CollectionAgentNodeLink.collection_agent_id == agent.id)
            .all()
        )
        rules = (
            session.query(CollectionAgentMatchRule)
            .filter(CollectionAgentMatchRule.collection_agent_id == agent.id)
            .all()
        )

        explicit_node_ids = [link.node_id for link in node_links]
        rule_matched_ids = self._resolve_rule_nodes(session, rules)
        resolved = sorted(set(explicit_node_ids) | rule_matched_ids)

        return CollectionAgentResponse(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            interval_seconds=agent.interval_seconds,
            enabled=agent.enabled,
            config_revision=agent.config_revision or 0,
            last_manifest_poll=agent.last_manifest_poll,
            acked_revision=agent.acked_revision or 0,
            acked_at=agent.acked_at,
            nodes=explicit_node_ids,
            rules=[
                CollectionAgentMatchRuleResponse(
                    id=r.id, site=r.site, vendor=r.vendor,
                    os=r.os, status=r.status, role=r.role,
                )
                for r in rules
            ],
            resolved_nodes=resolved,
        )

    # --- CRUD ---

    def create(self, payload: CollectionAgentCreate) -> CollectionAgentResponse:
        session = next(self.db.get_session())
        try:
            agent = CollectionAgent(
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
    ) -> List[CollectionAgentResponse]:
        session = next(self.db.get_session())
        try:
            query = session.query(CollectionAgent)
            if name is not None:
                query = query.filter(CollectionAgent.name.ilike(f"{name}%"))
            if enabled is not None:
                query = query.filter(CollectionAgent.enabled == enabled)
            agents = query.all()
            return [self._get_agent_response(session, agent) for agent in agents]
        finally:
            session.close()

    def get(self, id: int) -> CollectionAgentResponse:
        session = next(self.db.get_session())
        try:
            agent = session.get(CollectionAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="CollectionAgent not found")
            return self._get_agent_response(session, agent)
        finally:
            session.close()

    def update(self, id: int, payload: CollectionAgentUpdate) -> CollectionAgentResponse:
        session = next(self.db.get_session())
        try:
            agent = session.get(CollectionAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="CollectionAgent not found")

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
            agent = session.get(CollectionAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="CollectionAgent not found")

            session.query(CollectionAgentNodeLink).filter(
                CollectionAgentNodeLink.collection_agent_id == id
            ).delete()
            session.query(CollectionAgentMatchRule).filter(
                CollectionAgentMatchRule.collection_agent_id == id
            ).delete()

            session.delete(agent)
            session.commit()
        finally:
            session.close()

    # --- Node mapping ---

    def add_node(self, id: int, node_id: int) -> None:
        session = next(self.db.get_session())
        try:
            agent = session.get(CollectionAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="CollectionAgent not found")

            node = session.get(Node, node_id)
            if not node:
                raise HTTPException(status_code=404, detail="Node not found")

            existing = (
                session.query(CollectionAgentNodeLink)
                .filter(
                    CollectionAgentNodeLink.collection_agent_id == id,
                    CollectionAgentNodeLink.node_id == node_id,
                )
                .first()
            )
            if existing:
                raise HTTPException(status_code=409, detail="Node already assigned to this collection agent")

            link = CollectionAgentNodeLink(collection_agent_id=id, node_id=node_id)
            session.add(link)
            self._bump_revision(session, id)
            session.commit()
        finally:
            session.close()

    def remove_node(self, id: int, node_id: int) -> None:
        session = next(self.db.get_session())
        try:
            link = (
                session.query(CollectionAgentNodeLink)
                .filter(
                    CollectionAgentNodeLink.collection_agent_id == id,
                    CollectionAgentNodeLink.node_id == node_id,
                )
                .first()
            )
            if not link:
                raise HTTPException(status_code=404, detail="Node not assigned to this collection agent")

            session.delete(link)
            self._bump_revision(session, id)
            session.commit()
        finally:
            session.close()

    # --- Match rules ---

    def add_rule(self, id: int, payload: CollectionAgentMatchRuleCreate) -> CollectionAgentMatchRuleResponse:
        session = next(self.db.get_session())
        try:
            agent = session.get(CollectionAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="CollectionAgent not found")

            rule = CollectionAgentMatchRule(
                collection_agent_id=id,
                site=payload.site, vendor=payload.vendor,
                os=payload.os, status=payload.status, role=payload.role,
            )
            session.add(rule)
            self._bump_revision(session, id)
            session.commit()
            session.refresh(rule)
            return CollectionAgentMatchRuleResponse(
                id=rule.id, site=rule.site, vendor=rule.vendor,
                os=rule.os, status=rule.status, role=rule.role,
            )
        finally:
            session.close()

    def remove_rule(self, id: int, rule_id: int) -> None:
        session = next(self.db.get_session())
        try:
            rule = (
                session.query(CollectionAgentMatchRule)
                .filter(
                    CollectionAgentMatchRule.id == rule_id,
                    CollectionAgentMatchRule.collection_agent_id == id,
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

    def ack_manifest(self, id: int, payload: CollectionAgentAck) -> dict:
        session = next(self.db.get_session())
        try:
            agent = session.get(CollectionAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="CollectionAgent not found")
            agent.acked_revision = payload.config_revision
            agent.acked_at = datetime.utcnow().isoformat()
            session.commit()
            return {"status": "ok", "acked_revision": agent.acked_revision}
        finally:
            session.close()

    # --- Manifest ---

    def get_manifest(self, id: int) -> dict:
        session = next(self.db.get_session())
        try:
            agent = session.get(CollectionAgent, id)
            if not agent:
                raise HTTPException(status_code=404, detail="CollectionAgent not found")

            # Resolve nodes
            node_links = (
                session.query(CollectionAgentNodeLink)
                .filter(CollectionAgentNodeLink.collection_agent_id == id)
                .all()
            )
            explicit_ids = {link.node_id for link in node_links}

            rules = (
                session.query(CollectionAgentMatchRule)
                .filter(CollectionAgentMatchRule.collection_agent_id == id)
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

            # Node ↔ Credential mappings {node_id: {credential_type: credential_id}}
            node_creds = (
                session.query(NodeCredential)
                .filter(NodeCredential.node_id.in_(all_node_ids))
                .all()
            ) if all_node_ids else []
            cred_ids = {nc.credential_id for nc in node_creds}
            cred_map = {c.id: c for c in session.query(Credential).filter(Credential.id.in_(cred_ids)).all()} if cred_ids else {}
            node_cred_map = {}
            for nc in node_creds:
                cred = cred_map.get(nc.credential_id)
                if cred:
                    node_cred_map.setdefault(nc.node_id, {})[cred.credential_type] = nc.credential_id

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
                    "credentials": node_cred_map.get(node.id, {}),
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
