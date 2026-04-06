import inspect
from acex.models import Asset, AssetResponse, PaginatedResponse
from typing import List


class AssetService:
    """Service layer för Asset business logic."""

    def __init__(self, adapter):
        self.adapter = adapter

    async def _call_method(self, method, *args, **kwargs):
        """Helper för att hantera både sync och async metoder."""
        if inspect.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        else:
            return method(*args, **kwargs)

    async def create(self, asset: Asset):
        result = await self._call_method(self.adapter.create, asset)
        return result

    async def get(self, id: str) -> AssetResponse:
        result = await self._call_method(self.adapter.get, id)
        return result

    async def query(
        self,
        vendor: str = None,
        os: str = None,
        hardware_model: str = None,
        ned_id: str = None,
        serial_number: str = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse[AssetResponse]:

        query_filters = {
            k: v for k, v in {
                "vendor": vendor,
                "os": os,
                "hardware_model": hardware_model,
                "serial_number": serial_number,
                "ned_id": ned_id,
            }.items() if v is not None
        }

        result = await self._call_method(self.adapter.query, filters=query_filters, limit=limit, offset=offset)
        return PaginatedResponse(items=result["items"], total=result["total"], limit=limit, offset=offset)

    async def update(self, id: str, asset: Asset):
        result = await self._call_method(self.adapter.update, id, asset)
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
