import inspect
from acex.models.contacts import Contact, ContactBase, ContactResponse
from acex.models.pagination import PaginatedResponse
from typing import List


class ContactService:
    """Service layer för Contact business logic."""

    def __init__(self, adapter):
        self.adapter = adapter

    async def _call_method(self, method, *args, **kwargs):
        """Helper för att hantera både sync och async metoder."""
        if inspect.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        else:
            return method(*args, **kwargs)

    async def create(self, contact: ContactBase):
        result = await self._call_method(self.adapter.create, Contact(**contact.model_dump()))
        return result

    async def get(self, id: str) -> ContactResponse:
        result = await self._call_method(self.adapter.get, id)
        return result

    async def query(
        self,
        name: str = None,
        display_name: str = None,
        first_name: str = None,
        family_name: str = None,
        email: str = None,
        role: str = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse[ContactResponse]:

        query_filters = {
            k: v for k, v in {
                "name": name,
                "display_name": display_name,
                "first_name": first_name,
                "family_name": family_name,
                "email": email,
                "role": role,
            }.items() if v is not None
        }

        result = await self._call_method(self.adapter.query, filters=query_filters, limit=limit, offset=offset)
        return PaginatedResponse(items=result["items"], total=result["total"], limit=limit, offset=offset)

    async def update(self, id: str, contact: Contact):
        result = await self._call_method(self.adapter.update, id, contact)
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
