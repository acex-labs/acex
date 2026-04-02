import inspect
from acex.models.sites import Site, SiteBase, SiteResponse
from typing import List


class SiteService:
    """Service layer för Site business logic."""

    def __init__(self, adapter, inventory=None):
        self.adapter = adapter
        self.inventory = inventory

    async def _call_method(self, method, *args, **kwargs):
        """Helper för att hantera både sync och async metoder."""
        if inspect.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        else:
            return method(*args, **kwargs)

    async def _enrich_data(self, site):
        """Berika site med tillhörande kontakter via assignments."""
        if site is None:
            return None
        data = site.model_dump() if hasattr(site, 'model_dump') else dict(site)
        contacts = []
        if self.inventory and hasattr(self.inventory, 'contact_assignment_manager'):
            assignments = self.inventory.contact_assignment_manager.list_assignments(site_name=site.name)
            for a in assignments:
                result = await self.inventory.contacts.query(name=a.contact_name)
                if result:
                    contacts.append(result[0])
        data["contacts"] = contacts
        return SiteResponse(**data)

    async def create(self, site: SiteBase):
        result = await self._call_method(self.adapter.create, Site(**site.model_dump()))
        return result

    async def get(self, id: str) -> SiteResponse:
        result = await self._call_method(self.adapter.get, id)
        return await self._enrich_data(result)

    async def query(
        self,
        name: str = None,
        display_name: str = None,
        city: str = None,
        country: str = None,
    ) -> List[SiteResponse]:

        query_filters = {
            k: v for k, v in {
                "name": name,
                "display_name": display_name,
                "city": city,
                "country": country,
            }.items() if v is not None
        }

        result = await self._call_method(self.adapter.query, filters=query_filters)
        return [await self._enrich_data(s) for s in result]

    async def update(self, id: str, site: Site):
        result = await self._call_method(self.adapter.update, id, site)
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
