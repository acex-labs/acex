
from .adapter_base import AdapterBase
from acex.models.contacts import Contact, ContactResponse


class ContactAdapter(AdapterBase):

    def create(self, contact: Contact):
        if hasattr(self.plugin, "create"):
            return getattr(self.plugin, "create")(contact)

    def get(self, id: str) -> ContactResponse:
        if hasattr(self.plugin, "get"):
            return getattr(self.plugin, "get")(id)

    def query(self, filters: dict = None, limit: int = 100, offset: int = 0) -> list[ContactResponse]:
        if hasattr(self.plugin, "query"):
            return getattr(self.plugin, "query")(filters, limit=limit, offset=offset)

    def update(self, id: str, contact: Contact):
        if hasattr(self.plugin, "update"):
            return getattr(self.plugin, "update")(id, contact)

    def delete(self, id: str):
        if hasattr(self.plugin, "delete"):
            return getattr(self.plugin, "delete")(id)
