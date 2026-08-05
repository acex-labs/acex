from acex.models.sites import Site, SiteResponse

from .adapter_base import AdapterBase


class SiteAdapter(AdapterBase):
    def create(self, site: Site):
        if hasattr(self.plugin, "create"):
            return self.plugin.create(site)

    def get(self, id: str) -> SiteResponse:
        if hasattr(self.plugin, "get"):
            return self.plugin.get(id)

    def query(self, filters: dict = None, limit: int = 100, offset: int = 0) -> list[SiteResponse]:
        if hasattr(self.plugin, "query"):
            return self.plugin.query(filters, limit=limit, offset=offset)

    def update(self, id: str, site: Site):
        if hasattr(self.plugin, "update"):
            return self.plugin.update(id, site)

    def delete(self, id: str):
        if hasattr(self.plugin, "delete"):
            return self.plugin.delete(id)
