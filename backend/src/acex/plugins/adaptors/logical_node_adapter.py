
from .adapter_base import AdapterBase
from acex.models import LogicalNode, LogicalNodeResponse, LogicalNodeListResponse


class LogicalNodeAdapter(AdapterBase):

    def create(self, logical_node: LogicalNode): 
        if hasattr(self.plugin, "create"):
            return getattr(self.plugin, "create")(logical_node)

    def get(self, identitet: str) -> LogicalNodeResponse: 
        if hasattr(self.plugin, "get"):
            return getattr(self.plugin, "get")(identitet)

    def query(self, filters: dict = None, extra_filters: list = None, limit: int = 100, offset: int = 0) -> list[LogicalNodeListResponse]:
        if hasattr(self.plugin, "query"):
            return getattr(self.plugin, "query")(filters, extra_filters=extra_filters, limit=limit, offset=offset)

    def update(self, id: str, logical_node: LogicalNode): 
        if hasattr(self.plugin, "update"):
            return getattr(self.plugin, "update")(id, logical_node)

    def delete(self, id: str): 
        if hasattr(self.plugin, "delete"):
            return getattr(self.plugin, "delete")(id)
