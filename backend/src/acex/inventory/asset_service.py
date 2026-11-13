import inspect
from typing import Literal

from acex.models import Asset
from acex.models.node import Node
from acex_devkit.models.asset import AssetResponse, AssetUpdate
from acex_devkit.models.node_response import AssetRefType
from acex_devkit.models.os_version import OsVersionScheme
from acex_devkit.models.pagination import PaginatedResponse
from fastapi import HTTPException
from sqlalchemy import String, cast, or_, select


class AssetService:
    """Service layer för Asset business logic."""

    SORTABLE_COLUMNS = {
        "id": "id",
        "vendor": "vendor",
        "os": "os",
        "hardware_model": "hardware_model",
        "serial_number": "serial_number",
        "ned_id": "ned_id",
        "os_version": "os_version",
    }

    # What ``q`` is looked for in: the fields that identify an asset to a person,
    # i.e. what a picker shows as its title (vendor, model) and sublabel (driver, serial).
    SEARCHABLE_COLUMNS = (Asset.serial_number, Asset.hardware_model, Asset.vendor, Asset.ned_id)

    def __init__(self, adapter, hardware_models):
        self.adapter = adapter
        # An asset entering the inventory enables its hardware model.
        self.hardware_models = hardware_models

    async def _call_method(self, method, *args, **kwargs):
        """Helper för att hantera både sync och async metoder."""
        if inspect.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        else:
            return method(*args, **kwargs)

    async def create(self, asset: Asset):
        result = await self._call_method(self.adapter.create, asset)
        self.hardware_models.enable_for_asset(asset.hardware_model, enabled_by="inventory")
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
        sort: str | None = None,
        order: Literal["asc", "desc"] = "asc",
        q: str | None = None,
    ) -> PaginatedResponse[AssetResponse]:
        """List assets, filtered by the per-field params and/or ``q``.

        ``q`` is one search text matched, case-insensitively as a contains, against
        serial number, hardware model, vendor and NED id. It narrows the result
        together with every other filter, and ``total`` counts only what matches.
        """

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
        if q is not None and q.strip():
            text = q.strip()
            # autoescape: a typed % or _ is that character, not a wildcard.
            # cast: vendor is an enum in the model, and contains needs text on every database.
            extra_filters.append(
                or_(*(cast(column, String).icontains(text, autoescape=True) for column in self.SEARCHABLE_COLUMNS))
            )
        sort_column = None
        if sort is not None:
            sort_column = self.SORTABLE_COLUMNS.get(sort)
            if sort_column is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid sort field '{sort}'. Valid: {sorted(self.SORTABLE_COLUMNS)}",
                )
        result = await self._call_method(
            self.adapter.query,
            filters=query_filters,
            extra_filters=extra_filters or None,
            limit=limit,
            offset=offset,
            sort=sort_column,
            order=order,
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
        if "hardware_model" in patch:
            self.hardware_models.enable_for_asset(patch["hardware_model"], enabled_by="inventory")
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
