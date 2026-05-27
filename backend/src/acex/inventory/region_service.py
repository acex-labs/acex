import inspect
from acex.models.regions import Region, RegionBase, RegionResponse, RegionSiteInfo
from acex.models.pagination import PaginatedResponse


class RegionService:

    def __init__(self, adapter, inventory=None):
        self.adapter = adapter
        self.inventory = inventory

    async def _call_method(self, method, *args, **kwargs):
        if inspect.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        else:
            return method(*args, **kwargs)

    async def _enrich_data(self, region):
        if region is None:
            return None
        data = region.model_dump() if hasattr(region, 'model_dump') else dict(region)
        sites = []
        if self.inventory and hasattr(self.inventory, 'region_assignment_manager'):
            assignments = self.inventory.region_assignment_manager.list_assignments(region_name=region.name)
            for a in assignments:
                result = await self.inventory.sites.query(name=a.site_name)
                if result.items:
                    s = result.items[0]
                    sites.append(RegionSiteInfo(
                        name=s.name,
                        display_name=s.display_name,
                        city=s.city,
                        country=s.country,
                        latitude=s.latitude,
                        longitude=s.longitude,
                    ))
        data["sites"] = sites
        return RegionResponse(**data)

    async def create(self, region: RegionBase):
        result = await self._call_method(self.adapter.create, Region(**region.model_dump()))
        return result

    async def get(self, id: str) -> RegionResponse:
        result = await self._call_method(self.adapter.get, id)
        return await self._enrich_data(result)

    async def query(
        self,
        name: str = None,
        display_name: str = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse[RegionResponse]:

        query_filters = {
            k: v for k, v in {
                "name": name,
                "display_name": display_name,
            }.items() if v is not None
        }

        result = await self._call_method(self.adapter.query, filters=query_filters, limit=limit, offset=offset)
        items = [await self._enrich_data(r) for r in result["items"]]
        return PaginatedResponse(items=items, total=result["total"], limit=limit, offset=offset)

    async def update(self, id: str, region: Region):
        result = await self._call_method(self.adapter.update, id, region)
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
