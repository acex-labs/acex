import inspect
from typing import List, Optional

from sqlalchemy import select

from acex.models import LogicalNode, LogicalNodeResponse, LogicalNodeListResponse, LogicalNodeConfigResponse, PaginatedResponse
from acex.models.node import Node
from acex.models.regions import SiteRegionAssignment


class LogicalNodeService:
    """Service layer för LogicalNode business logic inklusive kompilering."""

    def __init__(self, adapter, config_compiler, integrations, db_manager=None):
        self.adapter = adapter
        self.config_compiler = config_compiler
        self.integrations = integrations
        self.db_manager = db_manager
    
    async def _call_method(self, method, *args, **kwargs):
        """Helper för att hantera både sync och async metoder."""
        if inspect.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        else:
            return method(*args, **kwargs)
    
    async def _apply_compilation(self, logical_node, resolve:bool = False):
        """Helper för att applicera kompilering sync eller async."""
        if self.config_compiler and logical_node:
            if inspect.iscoroutinefunction(self.config_compiler.compile):
                return await self.config_compiler.compile(logical_node, self.integrations, resolve)
            else:
                return self.config_compiler.compile(logical_node, self.integrations, resolve)
        return logical_node
    
    async def create(self, logical_node: LogicalNode):
        result = await self._call_method(self.adapter.create, logical_node)
        return result
    
    async def _get_regions(self, site: str) -> list[str]:
        if not site or not self.db_manager:
            return []
        session = next(self.db_manager.get_session())
        try:
            assignments = session.query(SiteRegionAssignment).filter(
                SiteRegionAssignment.site_name == site
            ).all()
            return [a.region_name for a in assignments]
        finally:
            session.close()

    async def get(self, id: str) -> LogicalNodeResponse:
        ln = await self._call_method(self.adapter.get, id)
        regions = await self._get_regions(ln.site if ln else None)
        return LogicalNodeResponse(**ln.model_dump(), regions=regions)

    async def get_configuration(self, id: str, resolve: bool = False) -> LogicalNodeConfigResponse:
        ln = await self._call_method(self.adapter.get, id)
        compiled = await self._apply_compilation(ln, resolve=resolve)
        regions = await self._get_regions(ln.site if ln else None)
        return compiled.config_response.model_copy(update={"regions": regions})
    
    async def query(
        self,
        role: str = None,
        site: str = None,
        region: str = None,
        sequence: int = None,
        hostname: str = None,
        assigned: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse[LogicalNodeListResponse]:

        query_filters = {
            k: v for k, v in {
                "role": role,
                "sequence": sequence,
                "hostname": hostname,
            }.items() if v is not None
        }

        if region and self.db_manager:
            session = next(self.db_manager.get_session())
            try:
                site_names = [
                    row[0] for row in session.query(SiteRegionAssignment.site_name)
                    .filter(SiteRegionAssignment.region_name == region)
                    .all()
                ]
            finally:
                session.close()
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

        result = await self._call_method(self.adapter.query, filters=query_filters, extra_filters=extra_filters or None, limit=limit, offset=offset)

        # Bulk enrich with region memberships
        items_raw = result["items"]
        site_region_map: dict = {}
        if self.db_manager:
            unique_sites = list({ln.site for ln in items_raw if ln.site})
            if unique_sites:
                session = next(self.db_manager.get_session())
                try:
                    assignments = session.query(SiteRegionAssignment).filter(
                        SiteRegionAssignment.site_name.in_(unique_sites)
                    ).all()
                    for a in assignments:
                        site_region_map.setdefault(a.site_name, []).append(a.region_name)
                finally:
                    session.close()

        items = []
        for ln in items_raw:
            ln_data = ln.model_dump()
            ln_data['regions'] = site_region_map.get(ln.site, []) if ln.site else []
            items.append(LogicalNodeListResponse(**ln_data))

        return PaginatedResponse(items=items, total=result["total"], limit=limit, offset=offset)
    
    async def update(self, id: str, logical_node: LogicalNode):
        result = await self._call_method(self.adapter.update, id, logical_node)
        return result
    
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
