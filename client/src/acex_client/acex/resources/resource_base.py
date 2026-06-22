from __future__ import annotations
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class PaginatedResult:
    def __init__(self, items, total, limit, offset):
        self.items = items
        self.total = total
        self.limit = limit
        self.offset = offset

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __bool__(self):
        return len(self.items) > 0


class LiveInstance(Generic[T]):
    """Mutable proxy around a Pydantic model with .save() and .delete() support."""

    def __init__(self, model: T, resource: Resource):
        object.__setattr__(self, "_data", model.model_dump())
        object.__setattr__(self, "_original", model.model_dump())
        object.__setattr__(self, "_resource", resource)

    def __getattr__(self, name: str) -> Any:
        try:
            return object.__getattribute__(self, "_data")[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        object.__getattribute__(self, "_data")[name] = value

    def __repr__(self) -> str:
        data = object.__getattribute__(self, "_data")
        resource = object.__getattribute__(self, "_resource")
        return f"{resource.__class__.__name__}({data})"

    def save(self) -> LiveInstance[T]:
        data = object.__getattribute__(self, "_data")
        original = object.__getattribute__(self, "_original")
        resource = object.__getattribute__(self, "_resource")
        changed = {k: v for k, v in data.items() if k != "id" and v != original.get(k)}
        if changed:
            updated = resource.update(data["id"], **changed)
            object.__setattr__(self, "_data", updated.model_dump())
            object.__setattr__(self, "_original", updated.model_dump())
        return self

    def delete(self) -> None:
        data = object.__getattribute__(self, "_data")
        resource = object.__getattribute__(self, "_resource")
        resource.delete(data["id"])


class Resource:
    def __init__(self, rest_client):
        self.rest = rest_client

    @property
    def ep(self):
        return self.__class__.ENDPOINT

    @property
    def list_model(self):
        return self.__class__.RESPONSE_MODEL_LIST

    @property
    def single_model(self):
        return self.__class__.RESPONSE_MODEL_SINGLE


class GetMixin:
    def get(self, id) -> LiveInstance | None:
        data = self.rest.get_item(self.ep, id)
        if data is not None:
            return LiveInstance(self.single_model(**data), self)
        return None


class ListMixin:
    def query(self, limit=100, offset=0, **filters) -> PaginatedResult:
        params = {k: v for k, v in filters.items() if v is not None}
        params["limit"] = limit
        params["offset"] = offset
        data = self.rest.query_items(self.ep, params=params)
        if isinstance(data, dict) and "items" in data:
            items = [self.list_model(**item) for item in data["items"]]
            return PaginatedResult(items, data["total"], data["limit"], data["offset"])
        if isinstance(data, list):
            items = [self.list_model(**item) for item in data]
            return PaginatedResult(items, len(items), len(items), 0)
        return PaginatedResult([], 0, limit, offset)

    def get_all(self):
        return self.query().items


class CreateMixin:
    def create(self, **kwargs) -> LiveInstance:
        data = self.rest.post(self.ep, json=kwargs)
        return LiveInstance(self.single_model(**data), self)


class UpdateMixin:
    def update(self, id, **kwargs):
        data = self.rest.patch(self.ep, id, json=kwargs)
        return self.single_model(**data)


class DeleteMixin:
    def delete(self, id) -> None:
        self.rest.delete(self.ep, id)
