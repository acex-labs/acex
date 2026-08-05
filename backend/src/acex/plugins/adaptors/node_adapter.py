from acex.models import Node, NodeResponse
from sqlalchemy.orm import joinedload

from .adapter_base import AdapterBase


class NodeAdapter(AdapterBase):
    def create(self, node: Node):
        if hasattr(self.plugin, "create"):
            return self.plugin.create(node)

    def get(self, id: str) -> NodeResponse:
        if hasattr(self.plugin, "get"):
            return self.plugin.get(id)

    def query(self, filters: dict = None, limit: int = 100, offset: int = 0) -> list[Node]:
        if hasattr(self.plugin, "query"):
            return self.plugin.query(
                filters,
                options=[joinedload(Node.logical_node)],
                limit=limit,
                offset=offset,
            )

    def update(self, id: str, node: Node):
        if hasattr(self.plugin, "update"):
            return self.plugin.update(id, node)

    def delete(self, id: str):
        if hasattr(self.plugin, "delete"):
            return self.plugin.delete(id)
