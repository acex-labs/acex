import inspect

from acex.inventory.region_assignment_manager import site_names_in_region
from acex.inventory.uniqueness import LOGICAL_NODE_HOSTNAME, as_id, require_text, unique
from acex.models import LogicalNode
from acex.models.node import Node
from acex.models.regions import SiteRegionAssignment
from acex.utils.identity import key_of
from acex_devkit.models.logical_node import LogicalNodeConfigResponse, LogicalNodeListResponse, LogicalNodeResponse
from acex_devkit.models.pagination import PaginatedResponse
from fastapi import HTTPException
from sqlmodel import select


class LogicalNodeService:
    """Service layer för LogicalNode business logic inklusive kompilering."""

    def __init__(self, adapter, config_compiler, integrations, db_manager=None, telemetry_agent_manager=None):
        self.adapter = adapter
        self.config_compiler = config_compiler
        self.integrations = integrations
        self.db_manager = db_manager
        self.telemetry_agent_manager = telemetry_agent_manager

    async def _call_method(self, method, *args, **kwargs):
        """Helper för att hantera både sync och async metoder."""
        if inspect.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        else:
            return method(*args, **kwargs)

    async def _apply_compilation(self, logical_node, resolve: bool = False):
        """Helper för att applicera kompilering sync eller async."""
        if self.config_compiler and logical_node:
            if inspect.iscoroutinefunction(self.config_compiler.compile):
                return await self.config_compiler.compile(logical_node, self.integrations, resolve)
            else:
                return self.config_compiler.compile(logical_node, self.integrations, resolve)
        return logical_node

    async def create(self, logical_node: LogicalNode):
        """Add a logical node; 409 if its hostname is taken."""
        logical_node.hostname = require_text(logical_node.hostname, "hostname")
        async with unique(self.adapter, LOGICAL_NODE_HOSTNAME, logical_node.hostname):
            result = await self._call_method(self.adapter.create, logical_node)
        return result

    async def _get_regions(self, site: str) -> list[str]:
        if not site or not self.db_manager:
            return []
        session = next(self.db_manager.get_session())
        try:
            assignments = session.exec(select(SiteRegionAssignment).where(SiteRegionAssignment.site_name == site)).all()
            return [a.region_name for a in assignments]
        finally:
            session.close()

    async def get(self, id: str) -> LogicalNodeResponse:
        ln = await self._call_method(self.adapter.get, id)
        regions = await self._get_regions(ln.site if ln else None)
        return LogicalNodeResponse(**ln.model_dump(), regions=regions)

    async def compile(self, id: str, resolve: bool = False):
        """The logical node compiled: its composed configuration and the components behind it."""
        ln = await self._call_method(self.adapter.get, id)
        return await self._apply_compilation(ln, resolve=resolve)

    async def get_configuration(self, id: str, resolve: bool = False) -> LogicalNodeConfigResponse:
        compiled = await self.compile(id, resolve=resolve)
        regions = await self._get_regions(compiled.logical_node.site if compiled.logical_node else None)
        return compiled.config_response.model_copy(update={"regions": regions})

    async def query(
        self,
        role: str = None,
        site: str = None,
        region: str = None,
        sequence: int = None,
        hostname: str = None,
        assigned: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse[LogicalNodeListResponse]:

        query_filters = {
            k: v
            for k, v in {
                "role": role,
                "sequence": sequence,
                "hostname": hostname,
            }.items()
            if v is not None
        }

        if region and self.db_manager:
            site_names = site_names_in_region(self.db_manager, region)
            if not site_names:
                return PaginatedResponse(items=[], total=0, limit=limit, offset=offset)
            query_filters["site"] = site_names
        elif site is not None:
            query_filters["site"] = site

        extra_filters = []
        if assigned is not None:
            assigned_ids = select(Node.logical_node_id)
            if assigned:
                extra_filters.append(LogicalNode.id.in_(assigned_ids))
            else:
                extra_filters.append(~LogicalNode.id.in_(assigned_ids))

        result = await self._call_method(
            self.adapter.query, filters=query_filters, extra_filters=extra_filters or None, limit=limit, offset=offset
        )

        # Bulk enrich with region memberships
        items_raw = result["items"]
        site_region_map: dict = {}
        if self.db_manager:
            unique_sites = list({ln.site for ln in items_raw if ln.site})
            if unique_sites:
                session = next(self.db_manager.get_session())
                try:
                    assignments = session.exec(
                        select(SiteRegionAssignment).where(SiteRegionAssignment.site_name.in_(unique_sites))
                    ).all()
                    for a in assignments:
                        site_region_map.setdefault(a.site_name, []).append(a.region_name)
                finally:
                    session.close()

        items = []
        for ln in items_raw:
            ln_data = ln.model_dump()
            ln_data["regions"] = site_region_map.get(ln.site, []) if ln.site else []
            items.append(LogicalNodeListResponse(**ln_data))

        return PaginatedResponse(items=items, total=result["total"], limit=limit, offset=offset)

    def _node_ids(self, logical_node_id: str) -> list[int]:
        # External plugins may use non-integer IDs; those never link to Node rows.
        if not self.db_manager or not str(logical_node_id).isdigit():
            return []
        session = next(self.db_manager.get_session())
        try:
            return list(session.scalars(select(Node.id).where(Node.logical_node_id == int(logical_node_id))).all())
        finally:
            session.close()

    async def update(self, id: str, logical_node: LogicalNode):
        # A changed hostname must be free. One left as it is is not checked (the frontend sends every field).
        hostname = None
        hostname_changed = False
        if "hostname" in logical_node.model_fields_set:
            current = await self._call_method(self.adapter.get, id)
            if current is None:
                raise HTTPException(status_code=404, detail="Logical node not found")
            hostname = require_text(logical_node.hostname, "hostname")
            hostname_changed = key_of(hostname) != key_of(current.hostname)
            logical_node.hostname = hostname

        async with unique(
            self.adapter, LOGICAL_NODE_HOSTNAME, hostname, exclude_id=as_id(id), skip=not hostname_changed
        ):
            # site/role are telemetry rule fields — agents covering this logical
            # node's instances before or after the change get a new revision.
            if self.telemetry_agent_manager is None:
                return await self._call_method(self.adapter.update, id, logical_node)
            with self.telemetry_agent_manager.bumping_revisions_for_nodes(self._node_ids(id)):
                return await self._call_method(self.adapter.update, id, logical_node)

    async def delete(self, id: str):
        result = await self._call_method(self.adapter.delete, id)
        return result

    @property
    def capabilities(self):
        return self.adapter.capabilities

    def path(self, capability):
        return self.adapter.path(capability)

    def http_verb(self, capability):
        return self.adapter.http_verb(capability)
