from acex.models import LogicalNode, LogicalNodeListResponse, LogicalNodeResponse

from .adapter_base import AdapterBase


class LogicalNodeAdapter(AdapterBase):
    def create(self, logical_node: LogicalNode):
        if hasattr(self.plugin, "create"):
            return self.plugin.create(logical_node)

    def get(self, identitet: str) -> LogicalNodeResponse:
        if hasattr(self.plugin, "get"):
            return self.plugin.get(identitet)

    def query(
        self, filters: dict = None, extra_filters: list = None, limit: int = 100, offset: int = 0
    ) -> list[LogicalNodeListResponse]:
        if hasattr(self.plugin, "query"):
            return self.plugin.query(filters, extra_filters=extra_filters, limit=limit, offset=offset)

    def update(self, id: str, logical_node: LogicalNode):
        if hasattr(self.plugin, "update"):
            return self.plugin.update(id, logical_node)

    def delete(self, id: str):
        if hasattr(self.plugin, "delete"):
            return self.plugin.delete(id)
