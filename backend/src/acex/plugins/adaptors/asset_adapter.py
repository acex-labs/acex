from acex.models import Asset, AssetResponse

from .adapter_base import AdapterBase


class AssetAdapter(AdapterBase):
    def create(self, asset: Asset):
        if hasattr(self.plugin, "create"):
            return self.plugin.create(asset)

    def get(self, id: str) -> AssetResponse:
        if hasattr(self.plugin, "get"):
            return self.plugin.get(id)

    def query(
        self, filters: dict = None, extra_filters: list = None, limit: int = 100, offset: int = 0
    ) -> list[AssetResponse]:
        if hasattr(self.plugin, "query"):
            return self.plugin.query(filters, extra_filters=extra_filters, limit=limit, offset=offset)

    def update(self, id: str, asset: Asset):
        if hasattr(self.plugin, "update"):
            return self.plugin.update(id, asset)

    def delete(self, id: str):
        if hasattr(self.plugin, "delete"):
            return self.plugin.delete(id)
