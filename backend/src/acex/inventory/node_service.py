import inspect
import logging
from datetime import UTC, datetime
from typing import Literal

from acex.inventory.uniqueness import NODE_ASSET, NODE_CLUSTER, NODE_LOGICAL_NODE, unique
from acex.models import Asset, AssetCluster, ManagementConnection, Node
from acex.plugins.neds.manager.ned_manager import NEDManager
from acex.utils import collection_state
from acex_devkit.models.config_origin import AnnotatedConfigResponse, ComponentOrigin, OriginSpan
from acex_devkit.models.management_connection import ManagementConnectionResponse
from acex_devkit.models.node_response import AssetRefType, NodeAdminStatus, NodeInstance, NodeProvisionStatus
from acex_devkit.models.node_response import NodeListItem as NodeListResponse
from acex_devkit.models.pagination import PaginatedResponse
from fastapi import HTTPException
from sqlalchemy import Integer, case, cast, func, select
from sqlalchemy.dialects.postgresql import INET

log = logging.getLogger(__name__)


class NodeService:
    """Service layer för Node business logik."""

    SORTABLE_COLUMNS = {
        "id": "id",
        "hostname": "logical_node.hostname",
        "site": "logical_node.site",
        "role": "logical_node.role",
        "admin_status": "admin_status",
        "provision_status": "provision_status",
        "ip": "ip",
        "ned_id": "ned_id",
    }

    def __init__(self, adapter, inventory):
        self.adapter = adapter
        self.inventory = inventory

    async def _call_method(self, method, *args, **kwargs):
        """Helper för att hantera både sync och async metoder."""
        if inspect.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        else:
            return method(*args, **kwargs)

    def _collection_states(self, node_ids: list[int]) -> dict:
        """What the collection agents last found for these nodes. Nothing when there is no database to ask."""
        db = getattr(getattr(self.adapter, "plugin", None), "db", None)
        if db is None or not node_ids:
            return {}
        session = next(db.get_session())
        try:
            return collection_state.states_for(session, node_ids)
        finally:
            session.close()

    async def _enrich_data(self, node):
        """När en specific node hämtas vill vi,
        berika responsen med datat från refererade objekt."""
        if node is None:
            return None

        # A relationship, so model_dump() leaves it out; primary first, as nodes are listed.
        connections = sorted(getattr(node, "management_connections", None) or [], key=lambda c: (not c.primary, c.id))
        node = node.model_dump()
        node["management_connections"] = [c.model_dump() for c in connections]
        node["collection"] = self._collection_states([node["id"]]).get(node["id"])
        if node.get("asset_ref_type") == "asset_cluster":
            node["asset"] = self.inventory.asset_cluster_manager.get_cluster(node["asset_ref_id"]).model_dump()
        else:
            raw_asset = await self.inventory.assets.get(node["asset_ref_id"])
            if raw_asset:
                node["asset"] = {**raw_asset.model_dump(), "type": "asset"}
            else:
                node["asset"] = None
        ln = await self.inventory.logical_nodes.get(node["logical_node_id"])
        if ln is not None:
            node["logical_node"] = ln.model_dump()
            node["regions"] = ln.regions if ln.regions else []
        if self.inventory.credential_manager is not None:
            node["credentials"] = self.inventory.credential_manager.node_credential_refs(node["id"])
        return NodeInstance(**node)

    async def get_rendered_config(self, id: str):
        """
        Renderar konfigurationen för en nod instans.
        """
        ni = await self.get(id)
        compiled = await self.inventory.logical_nodes.compile(ni.logical_node_id)
        ned = NEDManager().get_driver_instance(ni.asset.ned_id)
        if ned is None:
            return "error: NED not found"
        try:
            return ned.render(compiled.config_response.configuration, ni).payload
        except Exception:
            log.exception(f"Rendering configuration for node instance {id} failed")
            return ""

    async def get_annotated_config(self, id: str) -> AnnotatedConfigResponse:
        """The rendered configuration with each block of text tied to the config component behind it."""
        ni = await self.get(id)
        compiled = await self.inventory.logical_nodes.compile(ni.logical_node_id)
        ned = NEDManager().get_driver_instance(ni.asset.ned_id)
        if ned is None:
            raise HTTPException(status_code=404, detail=f"No NED configured for node instance {id}")
        result = ned.render(compiled.config_response.configuration, ni)
        origins = compiled.configuration.origins()  # read after config_response, which places the components
        spans = [
            OriginSpan(**span.model_dump(), origin=self.origin(span.path, origins)) for span in result.metadata.spans
        ]
        return AnnotatedConfigResponse(content=result.payload, spans=spans)

    @staticmethod
    def origin(path: list[str], origins: list[ComponentOrigin]) -> ComponentOrigin | None:
        """The component whose path is the longest prefix of `path`: a line belongs to the most specific
        component placed at or above it."""
        matches = [o for o in origins if path[: len(o.path)] == o.path]
        return max(matches, key=lambda o: len(o.path), default=None)

    async def _require_logical_node(self, logical_node_id):
        """The logical node a node instance is for; 404 if there is none."""
        ln = await self._call_method(self.inventory.logical_nodes.adapter.get, logical_node_id)
        if ln is None:
            raise HTTPException(status_code=404, detail=f"Logical node {logical_node_id} not found")
        return ln

    async def _asset_ref(self, asset_ref_type, asset_ref_id):
        """The uniqueness rule and the name for what a node instance runs on; 404 if it does not exist."""
        if asset_ref_type == "asset_cluster":
            cluster = self.inventory.asset_cluster_manager.get_cluster(asset_ref_id)  # raises 404 itself
            return NODE_CLUSTER, cluster.name
        asset = await self.inventory.assets.get(asset_ref_id)
        if asset is None:
            raise HTTPException(status_code=404, detail=f"Asset {asset_ref_id} not found")
        return NODE_ASSET, asset.serial_number

    async def create(self, logical_node: Node) -> NodeInstance:
        """Add a node instance; 409 if its logical node or asset already has one."""
        asset_spec, asset_name = await self._asset_ref(logical_node.asset_ref_type, logical_node.asset_ref_id)
        ln = await self._require_logical_node(logical_node.logical_node_id)
        async with (
            unique(self.adapter, NODE_LOGICAL_NODE, logical_node.logical_node_id, subject=ln.hostname),
            unique(self.adapter, asset_spec, logical_node.asset_ref_id, subject=asset_name),
        ):
            result = await self._call_method(self.adapter.create, logical_node)
        node_id = getattr(result, "id", None)
        if node_id is not None:
            self.inventory.telemetry_agent_manager.bump_revisions_for_node(node_id)
        return await self._enrich_data(result)

    async def get(self, id: str) -> NodeInstance:
        result = await self._call_method(self.adapter.get, id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Node instance {id} not found")
        result = await self._enrich_data(result)
        return result

    async def query(
        self,
        site: str = None,
        region: str = None,
        hostname: str = None,
        management_connection_ip: str = None,
        logical_node_id: int = None,
        asset_ref_id: int = None,
        asset_ref_type: AssetRefType | None = None,
        vendor: str = None,
        os: str = None,
        role: str = None,
        admin_status: NodeAdminStatus | None = None,
        provision_status: NodeProvisionStatus | None = None,
        collection_status: Literal["ok", "failing", "unknown"] | None = None,
        collection_agent_id: int | None = None,
        limit: int | None = 100,  # None: every item
        offset: int = 0,
        sort: str | None = None,
        order: Literal["asc", "desc"] = "asc",
    ) -> PaginatedResponse[NodeListResponse]:

        query_filters = {
            k: v
            for k, v in {
                "logical_node.hostname": hostname,
                "logical_node.role": role,
                "logical_node_id": logical_node_id,
                "asset_ref_id": asset_ref_id,
                "asset_ref_type": asset_ref_type,
                "admin_status": admin_status,
                "provision_status": provision_status,
            }.items()
            if v is not None
        }

        if vendor or os:
            asset_resp = await self._call_method(self.inventory.assets.query, vendor=vendor, os=os, limit=10000)
            matching_ids = [a.id for a in asset_resp.items]
            if not matching_ids:
                return PaginatedResponse(items=[], total=0, limit=limit, offset=offset)
            existing = query_filters.get("asset_ref_id")
            if existing is not None:
                query_filters["asset_ref_id"] = [existing] if existing in matching_ids else []
                if not query_filters["asset_ref_id"]:
                    return PaginatedResponse(items=[], total=0, limit=limit, offset=offset)
            else:
                query_filters["asset_ref_id"] = matching_ids

        if region:
            site_names = self.inventory.region_assignment_manager.site_names_in(region)
            if not site_names:
                return PaginatedResponse(items=[], total=0, limit=limit, offset=offset)
            query_filters["logical_node.site"] = site_names
        elif site is not None:
            query_filters["logical_node.site"] = site

        extra_filters = []
        if management_connection_ip:
            extra_filters.append(
                Node.id.in_(
                    select(ManagementConnection.node_id).where(
                        ManagementConnection.target_ip.ilike(f"{management_connection_ip}%")
                    )
                )
            )
        if collection_status:
            extra_filters.append(collection_state.status_filter(collection_status))
        if collection_agent_id is not None:
            extra_filters.append(collection_state.agent_filter(collection_agent_id))
        extra_filters = extra_filters or None

        sort_column = "id"
        if sort is not None:
            if sort not in self.SORTABLE_COLUMNS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid sort field '{sort}'. Valid: {sorted(self.SORTABLE_COLUMNS)}",
                )
            if sort == "ip":
                # Order by the primary management connection's IP, numerically.
                # Non-IP values (hostnames, blanks) and nodes without a
                # connection become NULL and follow the database's NULL order.
                ip = ManagementConnection.target_ip
                if self.adapter.plugin.db.connection.backend == "postgresql":
                    numeric_ip = cast(ip, INET)
                else:
                    # No INET outside PostgreSQL: split the dotted quad on its dots and combine the octets.
                    rest, octets = ip, []
                    for _ in range(3):
                        dot = func.instr(rest, ".")
                        octets.append(cast(func.substr(rest, 1, dot - 1), Integer))
                        rest = func.substr(rest, dot + 1)
                    octets.append(cast(rest, Integer))
                    numeric_ip = ((octets[0] * 256 + octets[1]) * 256 + octets[2]) * 256 + octets[3]
                sort_column = (
                    select(
                        case(
                            (
                                ip.regexp_match(
                                    r"^((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$"
                                ),
                                numeric_ip,
                            ),
                            else_=None,
                        )
                    )
                    .where(ManagementConnection.node_id == Node.id)
                    .order_by(ManagementConnection.primary.desc(), ManagementConnection.id)
                    .limit(1)
                    .scalar_subquery()
                )
            elif sort == "ned_id":
                # Order by the referenced asset's (or asset cluster's) NED.
                # NULL ned_id sorts per Postgres defaults (last asc, first desc).
                sort_column = case(
                    (
                        Node.asset_ref_type == AssetRefType.asset,
                        select(Asset.ned_id).where(Asset.id == Node.asset_ref_id).scalar_subquery(),
                    ),
                    (
                        Node.asset_ref_type == AssetRefType.asset_cluster,
                        select(AssetCluster.ned_id).where(AssetCluster.id == Node.asset_ref_id).scalar_subquery(),
                    ),
                    else_=None,
                )
            else:
                sort_column = self.SORTABLE_COLUMNS[sort]

        result = await self._call_method(
            self.adapter.query,
            filters=query_filters,
            extra_filters=extra_filters,
            limit=limit,
            offset=offset,
            sort=sort_column,
            order=order,
        )

        # Bulk-fetch unique assets and clusters to avoid N+1
        asset_ids = {n.asset_ref_id for n in result["items"] if getattr(n, "asset_ref_type", "asset") == "asset"}
        cluster_ids = {n.asset_ref_id for n in result["items"] if getattr(n, "asset_ref_type", None) == "asset_cluster"}

        assets_by_id = {}
        for aid in asset_ids:
            asset = await self._call_method(self.inventory.assets.adapter.get, aid)
            if asset:
                assets_by_id[aid] = asset

        clusters_by_id = {}
        for cid in cluster_ids:
            cluster = self.inventory.asset_cluster_manager.get_cluster(cid)
            if cluster:
                clusters_by_id[cid] = cluster

        states = self._collection_states([n.id for n in result["items"]])

        items = []
        for node in result["items"]:
            if getattr(node, "asset_ref_type", "asset") == "asset_cluster":
                cluster = clusters_by_id.get(node.asset_ref_id)
                vendor = None
                os_val = None
                ned_id = cluster.ned_id if cluster else None
            else:
                asset = assets_by_id.get(node.asset_ref_id)
                vendor = asset.vendor if asset else None
                os_val = asset.os if asset else None
                ned_id = asset.ned_id if asset else None
            conns = sorted(node.management_connections or [], key=lambda c: (not c.primary, c.id))
            items.append(
                NodeListResponse(
                    **node.model_dump(),
                    hostname=node.logical_node.hostname if node.logical_node else None,
                    site=node.logical_node.site if node.logical_node else None,
                    role=node.logical_node.role if node.logical_node else None,
                    vendor=vendor,
                    os=os_val,
                    ned_id=ned_id,
                    management_connections=[ManagementConnectionResponse(**c.model_dump()) for c in conns],
                    collection=states.get(node.id),
                )
            )

        # Enrich with region memberships
        unique_sites = list({item.site for item in items if item.site})
        site_region_map: dict = {}
        if unique_sites and hasattr(self.inventory, "region_assignment_manager"):
            assignments = self.inventory.region_assignment_manager.list_assignments(site_names=unique_sites)
            for a in assignments:
                site_region_map.setdefault(a.site_name, []).append(a.region_name)
        for item in items:
            if item.site and item.site in site_region_map:
                item.regions = site_region_map[item.site]

        return PaginatedResponse(items=items, total=result["total"], limit=limit, offset=offset)

    async def update(self, id: str, logical_node: Node) -> NodeInstance:
        """Update the node instance and answer it as `get` does, so a client can read both the same way."""
        logical_node.updated_at = datetime.now(UTC)

        # Moving to another logical node, asset or cluster: the target must exist and be free. A patch that
        # leaves them as they are is not checked, so a node that already shares an asset stays editable.
        moved_to = subject = None
        ref_spec = ref_id = ref_name = None
        fields = logical_node.model_fields_set
        if fields & {"logical_node_id", "asset_ref_id", "asset_ref_type"}:
            current = await self._call_method(self.adapter.get, id)
            if current is None:
                raise HTTPException(status_code=404, detail=f"Node instance {id} not found")
            if "logical_node_id" in fields and logical_node.logical_node_id != current.logical_node_id:
                moved_to = logical_node.logical_node_id
                subject = (await self._require_logical_node(moved_to)).hostname
            ref_type = logical_node.asset_ref_type if "asset_ref_type" in fields else current.asset_ref_type
            ref_id = logical_node.asset_ref_id if "asset_ref_id" in fields else current.asset_ref_id
            if (ref_type, ref_id) != (current.asset_ref_type, current.asset_ref_id):
                ref_spec, ref_name = await self._asset_ref(ref_type, ref_id)

        async with (
            unique(
                self.adapter, NODE_LOGICAL_NODE, moved_to, exclude_id=int(id), skip=moved_to is None, subject=subject
            ),
            unique(self.adapter, ref_spec, ref_id, exclude_id=int(id), skip=ref_spec is None, subject=ref_name),
        ):
            # admin_status, provision_status and logical_node_id affect telemetry rule matching.
            with self.inventory.telemetry_agent_manager.bumping_revisions_for_nodes([int(id)]):
                await self._call_method(self.adapter.update, id, logical_node)
        return await self.get(id)

    async def delete(self, id: str):
        self.inventory.telemetry_agent_manager.bump_revisions_for_node(int(id))
        result = await self._call_method(self.adapter.delete, id)
        return result

    @property
    def capabilities(self):
        return self.adapter.capabilities

    def path(self, capability):
        return self.adapter.path(capability)

    def http_verb(self, capability):
        return self.adapter.http_verb(capability)
