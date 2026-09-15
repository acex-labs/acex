import inspect

from acex.models import Asset, AssetResponse, AssetUpdate, PaginatedResponse
from acex.models.node import AssetRefType, Node
from acex_devkit.models.os_version import OsVersionScheme
from fastapi import HTTPException
from sqlalchemy import select


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
        assigned: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse[AssetResponse]:

        query_filters = {
            k: v
            for k, v in {
                "vendor": vendor,
                "os": os,
                "hardware_model": hardware_model,
                "serial_number": serial_number,
                "ned_id": ned_id,
            }.items()
            if v is not None
        }

        extra_filters = []
        if assigned is not None:
            assigned_ids = select(Node.asset_ref_id).where(Node.asset_ref_type == AssetRefType.asset)
            if assigned:
                extra_filters.append(Asset.id.in_(assigned_ids))
            else:
                extra_filters.append(~Asset.id.in_(assigned_ids))

        result = await self._call_method(
            self.adapter.query, filters=query_filters, extra_filters=extra_filters or None, limit=limit, offset=offset
        )
        return PaginatedResponse(items=result["items"], total=result["total"], limit=limit, offset=offset)

    async def update(self, id: str, asset: AssetUpdate):
        """Apply a partial update, checking any field pair that must agree.

        ``os_version`` is only meaningful against an ``os``, and a patch may
        carry either one alone - so the stored asset supplies whichever half is
        missing before the pair is checked.
        """
        patch = asset.model_dump(exclude_unset=True)

        if "os" in patch or "os_version" in patch:
            current = await self._call_method(self.adapter.get, id)
            if current is None:
                raise HTTPException(status_code=404, detail="Asset not found")

            os_value = patch.get("os", current.os)
            version = patch.get("os_version", current.os_version)
            if version is not None:
                scheme = OsVersionScheme.for_os(os_value)
                if scheme is None:
                    raise HTTPException(status_code=422, detail=f"no version scheme declared for {os_value}")
                try:
                    patch["os_version"] = scheme.check(version)
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
                asset = asset.model_copy(update={"os_version": patch["os_version"]})

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
