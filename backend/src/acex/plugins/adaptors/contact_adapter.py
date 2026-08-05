from acex.models.contacts import Contact, ContactResponse

from .adapter_base import AdapterBase


class ContactAdapter(AdapterBase):
    def create(self, contact: Contact):
        if hasattr(self.plugin, "create"):
            return self.plugin.create(contact)

    def get(self, id: str) -> ContactResponse:
        if hasattr(self.plugin, "get"):
            return self.plugin.get(id)

    def query(self, filters: dict = None, limit: int = 100, offset: int = 0) -> list[ContactResponse]:
        if hasattr(self.plugin, "query"):
            return self.plugin.query(filters, limit=limit, offset=offset)

    def update(self, id: str, contact: Contact):
        if hasattr(self.plugin, "update"):
            return self.plugin.update(id, contact)

    def delete(self, id: str):
        if hasattr(self.plugin, "delete"):
            return self.plugin.delete(id)
