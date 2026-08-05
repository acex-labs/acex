from acex.models.regions import Region, RegionResponse

from .adapter_base import AdapterBase


class RegionAdapter(AdapterBase):
    def create(self, region: Region):
        if hasattr(self.plugin, "create"):
            return self.plugin.create(region)

    def get(self, id: str) -> RegionResponse:
        if hasattr(self.plugin, "get"):
            return self.plugin.get(id)

    def query(self, filters: dict = None, limit: int = 100, offset: int = 0) -> list[RegionResponse]:
        if hasattr(self.plugin, "query"):
            return self.plugin.query(filters, limit=limit, offset=offset)

    def update(self, id: str, region: Region):
        if hasattr(self.plugin, "update"):
            return self.plugin.update(id, region)

    def delete(self, id: str):
        if hasattr(self.plugin, "delete"):
            return self.plugin.delete(id)
