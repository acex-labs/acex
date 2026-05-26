from .adapter_base import AdapterBase
from acex.models.regions import Region, RegionResponse


class RegionAdapter(AdapterBase):

    def create(self, region: Region):
        if hasattr(self.plugin, "create"):
            return getattr(self.plugin, "create")(region)

    def get(self, id: str) -> RegionResponse:
        if hasattr(self.plugin, "get"):
            return getattr(self.plugin, "get")(id)

    def query(self, filters: dict = None, limit: int = 100, offset: int = 0) -> list[RegionResponse]:
        if hasattr(self.plugin, "query"):
            return getattr(self.plugin, "query")(filters, limit=limit, offset=offset)

    def update(self, id: str, region: Region):
        if hasattr(self.plugin, "update"):
            return getattr(self.plugin, "update")(id, region)

    def delete(self, id: str):
        if hasattr(self.plugin, "delete"):
            return getattr(self.plugin, "delete")(id)
