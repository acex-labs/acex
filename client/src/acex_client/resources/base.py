from __future__ import annotations

import inspect
import sys
import typing
from collections.abc import Iterator
from functools import wraps
from typing import Any, ClassVar

from pydantic import BaseModel

from acex_client.http import RestClient


class PaginatedResult:
    def __init__(self, items: list, total: int, limit: int, offset: int):
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

    def __getitem__(self, index):
        return self.items[index]


def _paginate(items, data, limit, offset) -> PaginatedResult:
    """Build a PaginatedResult from a `{items, total, limit, offset}` dict response."""
    return PaginatedResult(
        items,
        data.get("total", len(items)),
        data.get("limit", limit),
        data.get("offset", offset),
    )


class LiveInstance[G: BaseModel]:
    """Mutable proxy around a Pydantic model with .save() and .delete().

    Mutations go through Pydantic validation via `model_copy(update=...)`,
    so a wrong type is rejected immediately rather than silently swallowed
    until the next save round-trip.
    """

    def __init__(self, model: G, resource: Resource):
        object.__setattr__(self, "_model", model)
        object.__setattr__(self, "_original", model.model_dump())
        object.__setattr__(self, "_resource", resource)

    @property
    def id(self) -> Any:
        return self._model.id

    @property
    def model(self) -> G:
        return object.__getattribute__(self, "_model")

    def __getattr__(self, name: str) -> Any:
        resource = object.__getattribute__(self, "_resource")
        model = object.__getattribute__(self, "_model")
        sub_registry = type(resource)._SUB_RESOURCES
        if name in sub_registry:
            factory = sub_registry[name]
            return factory(resource.rest, parent_id=model.id)
        # Bound @action method declared on the resource class
        action_factory = type(resource)._ACTION_METHODS.get(name)
        if action_factory is not None:
            method, path_template, return_type = action_factory
            resource_path = getattr(resource, "path", "")
            bound_path = getattr(resource, "_path", None)
            if bound_path is not None:
                resource_path = resource_path
            # Resolve return type from the original wrapper function's annotation
            original_fn = getattr(type(resource), name, None)
            if original_fn is not None:
                return_type = _resolve_return_type(original_fn, return_type)
            meta = _ActionMeta(method, path_template, return_type, resource_path)
            return _BoundAction(meta, resource.rest, model.id)
        try:
            return getattr(model, name)
        except AttributeError:
            raise AttributeError(name) from None

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        model = object.__getattribute__(self, "_model")
        new_model = model.model_copy(update={name: value})
        object.__setattr__(self, "_model", new_model)

    def __repr__(self) -> str:
        model = object.__getattribute__(self, "_model")
        resource = object.__getattribute__(self, "_resource")
        return f"{resource.__class__.__name__}({model!r})"

    def save(self) -> LiveInstance[G]:
        model = object.__getattribute__(self, "_model")
        original = object.__getattribute__(self, "_original")
        resource = object.__getattribute__(self, "_resource")
        current = model.model_dump()
        changed = {k: v for k, v in current.items() if k != "id" and v != original.get(k)}
        if changed:
            updated = resource.update(model.id, **changed)
            object.__setattr__(self, "_original", updated.model_dump())
        return self

    def delete(self) -> None:
        model = object.__getattribute__(self, "_model")
        resource = object.__getattribute__(self, "_resource")
        resource.delete(model.id)


class _ResourceMeta(type):
    """Class metaclass that scans for methods decorated with @action/@sub_resource and
    populates _ACTION_METHODS / _SUB_RESOURCES on the class."""

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        actions: dict[str, tuple[str, str, Any]] = {}
        subs: dict[str, type] = {}
        for attr_name, attr_value in namespace.items():
            factory = getattr(attr_value, "_action_meta_factory", None)
            if factory is not None:
                actions[attr_name] = factory
            sub_type = getattr(attr_value, "_sub_resource_type", None)
            sub_name = getattr(attr_value, "_sub_resource_name", None)
            if sub_type is not None and sub_name is not None:
                subs[sub_name] = sub_type
        inherited_actions = getattr(cls, "_ACTION_METHODS", {})
        inherited_subs = getattr(cls, "_SUB_RESOURCES", {})
        cls._ACTION_METHODS = {**inherited_actions, **actions}
        cls._SUB_RESOURCES = {**inherited_subs, **subs}
        return cls


class Resource(metaclass=_ResourceMeta):
    """Base class for flat CRUD resources mounted at a single endpoint."""

    path: ClassVar[str]
    response_model: ClassVar[type[BaseModel]]
    list_model: ClassVar[type[BaseModel]]
    create_model: ClassVar[type[BaseModel]]
    update_model: ClassVar[type[BaseModel]]
    _SUB_RESOURCES: ClassVar[dict[str, Any]] = {}
    _ACTION_METHODS: ClassVar[dict[str, Any]] = {}

    def __init__(self, rest: RestClient):
        self.rest = rest

    def _make_live(self, model: BaseModel) -> LiveInstance:
        return LiveInstance(model, self)


class BoundResource(metaclass=_ResourceMeta):
    """Base class for sub-resources bound to a parent_id path segment."""

    path_template: ClassVar[str]
    response_model: ClassVar[type[BaseModel]]
    list_model: ClassVar[type[BaseModel]]
    create_model: ClassVar[type[BaseModel]]
    update_model: ClassVar[type[BaseModel]]

    def __init__(self, rest: RestClient, parent_id: Any):
        self.rest = rest
        self.parent_id = parent_id

    def _path(self, **extra: Any) -> str:
        return self.path_template.format(parent_id=self.parent_id, **extra)

    def _make_live(self, model: BaseModel) -> LiveInstance:
        return LiveInstance(model, self)


class GetMixin:
    def get(self, id: Any) -> LiveInstance:
        data = self.rest.request("GET", f"{self.path}/{id}")
        if data is None:
            from acex_client.exceptions import AcexNotFoundError

            raise AcexNotFoundError(404, f"{self.path}/{id} not found")
        return self._make_live(self.response_model(**data))


class BoundGetMixin:
    def get(self, id: Any) -> LiveInstance:
        path = self._path(id=id)
        data = self.rest.request("GET", path)
        if data is None:
            from acex_client.exceptions import AcexNotFoundError

            raise AcexNotFoundError(404, f"{path} not found")
        return self._make_live(self.response_model(**data))


class ListMixin:
    def query(self, limit: int = 100, offset: int = 0, **filters: Any) -> PaginatedResult:
        params = {k: v for k, v in filters.items() if v is not None}
        params["limit"] = limit
        params["offset"] = offset
        data = self.rest.request("GET", self.path, params=params)
        if isinstance(data, dict) and "items" in data:
            items = [self.list_model(**item) for item in data["items"]]
            return _paginate(items, data, limit, offset)
        if isinstance(data, list):
            items = [self.list_model(**item) for item in data]
            return PaginatedResult(items, len(items), len(items), 0)
        return PaginatedResult([], 0, limit, offset)

    def get_all(self) -> list:
        return self.query().items


class BoundListMixin:
    def query(self, limit: int = 100, offset: int = 0, **filters: Any) -> PaginatedResult:
        params = {k: v for k, v in filters.items() if v is not None}
        params["limit"] = limit
        params["offset"] = offset
        data = self.rest.request("GET", self._path(), params=params)
        if isinstance(data, dict) and "items" in data:
            items = [self.list_model(**item) for item in data["items"]]
            return _paginate(items, data, limit, offset)
        if isinstance(data, list):
            items = [self.list_model(**item) for item in data]
            return PaginatedResult(items, len(items), len(items), 0)
        return PaginatedResult([], 0, limit, offset)


class CreateMixin:
    def create(self, **body: Any) -> LiveInstance:
        validated = self.create_model(**body)
        payload = validated.model_dump(exclude_none=True)
        data = self.rest.request("POST", self.path, json=payload)
        return self._make_live(self.response_model(**data))


class BoundCreateMixin:
    def create(self, **body: Any) -> LiveInstance:
        validated = self.create_model(**body)
        payload = validated.model_dump(exclude_none=True)
        data = self.rest.request("POST", self._path(), json=payload)
        return self._make_live(self.response_model(**data))


class UpdateMixin:
    def update(self, id: Any, **body: Any) -> LiveInstance:
        validated = self.update_model(**body)
        payload = validated.model_dump(exclude_none=True)
        data = self.rest.request("PATCH", f"{self.path}/{id}", json=payload)
        return self._make_live(self.response_model(**data))


class DeleteMixin:
    def delete(self, id: Any) -> None:
        self.rest.request("DELETE", f"{self.path}/{id}")


class BoundDeleteMixin:
    def delete(self, **path_args: Any) -> None:
        # Build the path by formatting path_template with parent_id + any
        # extra path variables provided as kwargs. Common cases:
        #   /parent/{parent_id}/rules/{rule_id}    delete(rule_id=8)
        #   /parent/{parent_id}/nodes/{node_id}    delete(node_id=10)
        # If no path_args are provided, the delete targets the collection
        # itself (rare); we just format with parent_id.
        path_args.setdefault("parent_id", self.parent_id)
        path = self.path_template.format(**path_args)
        self.rest.request("DELETE", path)


class BoundUpdateMixin:
    def update(self, **path_and_body: Any) -> LiveInstance:
        """Update a bound sub-resource item.

        Path variables (matching names in path_template) are extracted;
        the rest are validated against `update_model` and sent as JSON body.
        """
        path_vars = _extract_path_vars(self.path_template)
        path_values: dict[str, Any] = {"parent_id": self.parent_id}
        body: dict[str, Any] = {}
        for name, value in path_and_body.items():
            if name in path_vars:
                path_values[name] = value
            else:
                body[name] = value
        path = self.path_template.format(**path_values)
        validated = self.update_model(**body)
        payload = validated.model_dump(exclude_none=True)
        data = self.rest.request("PATCH", path, json=payload)
        return self._make_live(self.response_model(**data))


class ActionMixin:
    """Marker mixin — enables @action-decorated methods on the resource."""

    pass


class _ActionMeta:
    """Metadata captured by @action at decoration time + invocation logic."""

    def __init__(self, method: str, path_template: str, return_type: Any = None, resource_path: str = ""):
        self.method = method.upper()
        self.path_template = path_template
        self.return_type = return_type
        self.resource_path = resource_path

    def invoke(self, rest: RestClient, **kwargs: Any) -> Any:
        path_vars = _extract_path_vars(self.path_template)
        path_values: dict[str, Any] = {}
        body: Any = None
        query: dict[str, Any] = {}
        for name, value in kwargs.items():
            if name in path_vars:
                path_values[name] = value
                continue
            if _is_body_value(value):
                body = _serialize_body(value)
                continue
            if value is not None:
                query[name] = value
        rendered_suffix = self.path_template.format(**path_values) if path_vars else self.path_template
        full_path = f"{self.resource_path}/{rendered_suffix}" if self.resource_path else rendered_suffix
        raw = self.return_type is str
        response = rest.request(self.method, full_path, params=query or None, json=body, raw=raw)
        return self._coerce(response)

    def _coerce(self, response: Any) -> Any:
        if response is None:
            return None
        rt = self.return_type
        if rt is None:
            return response
        if isinstance(rt, type) and issubclass(rt, str):
            return response
        origin = getattr(rt, "__origin__", None)
        if origin is list:
            inner = getattr(rt, "__args__", (Any,))[0]
            if isinstance(inner, type) and issubclass(inner, BaseModel):
                return [inner.model_validate(item) for item in response]
            return response
        if isinstance(rt, type) and issubclass(rt, BaseModel):
            return rt.model_validate(response)
        return response


class _BoundAction:
    """Callable bound to a parent_id — produced via LiveInstance.__getattr__."""

    def __init__(self, action_meta: _ActionMeta, rest: RestClient, parent_id: Any):
        self._meta = action_meta
        self._rest = rest
        self._parent_id = parent_id

    def __call__(self, **kwargs: Any) -> Any:
        kwargs.setdefault("id", self._parent_id)
        return self._meta.invoke(self._rest, **kwargs)


def action(method: str, path_template: str):
    """Decorator that marks a method on a Resource subclass as an HTTP action.

    The wrapped wrapper function resolves `resource_path` lazily at call time
    by checking `self.path` (so subclasses inheriting @action methods still
    use the right base path).

    Classification rules (introspection-free — based on the value passed in):
      * Name in path_template → path substitution ({id}/ack → id is path)
      * Pydantic BaseModel instance (or list of) → request body
      * Other non-None → query parameter
    """

    def decorator(fn):
        return_type = _get_return_annotation(fn)

        @wraps(fn)
        def wrapper(self, **kwargs: Any):
            resource_path = getattr(self, "path", "")
            bound_path = getattr(self, "_path", None)
            if bound_path is not None:
                # BoundResource instances use _path() instead of a plain path
                resource_path = self._path()
            resolved_return = _resolve_return_type(fn, return_type)
            meta = _ActionMeta(method, path_template, resolved_return, resource_path)
            return meta.invoke(self.rest, **kwargs)

        wrapper._action_meta_factory = (method, path_template, return_type)  # type: ignore[attr-defined]
        return wrapper

    return decorator


def stream(method: str, path_template: str):
    """Decorator that marks a method as an SSE-streaming action."""

    def decorator(fn):

        @wraps(fn)
        def wrapper(self, **kwargs: Any) -> Iterator[str]:
            resource_path = getattr(self, "path", "")
            bound_path = getattr(self, "_path", None)
            if bound_path is not None:
                resource_path = self._path()
            path_vars = _extract_path_vars(path_template)
            path_values: dict[str, Any] = {}
            body: Any = None
            query: dict[str, Any] = {}
            for name, value in kwargs.items():
                if name in path_vars:
                    path_values[name] = value
                elif _is_body_value(value):
                    body = _serialize_body(value)
                elif value is not None:
                    query[name] = value
            rendered_suffix = path_template.format(**path_values) if path_vars else path_template
            full_path = f"{resource_path}/{rendered_suffix}" if resource_path else rendered_suffix
            yield from self.rest.stream(method.upper(), full_path, params=query or None, json=body)

        wrapper._action_meta_factory = (method, path_template, None)  # type: ignore[attr-defined]
        return wrapper

    return decorator


def sub_resource(name: str):
    """Decorator that registers a method as returning a BoundResource.

    Used so a resource facade can expose e.g. `agents.rules(agent_id)` and
    so a LiveInstance can expose the same sub-resource via `agent.rules`.
    """

    def decorator(fn):
        return_type = _get_return_annotation(fn)

        @wraps(fn)
        def wrapper(self, parent_id: Any) -> Any:
            return return_type(self.rest, parent_id=parent_id)

        wrapper._sub_resource_name = name  # type: ignore[attr-defined]
        wrapper._sub_resource_type = return_type  # type: ignore[attr-defined]
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_path_vars(template: str) -> list[str]:
    """Extract {var} names from a path template like '{id}/ack'."""
    vars_: list[str] = []
    depth = 0
    current = ""
    for ch in template:
        if ch == "{":
            depth += 1
            current = ""
        elif ch == "}":
            if depth > 0:
                vars_.append(current)
                depth -= 1
            current = ""
        elif depth > 0:
            current += ch
    return vars_


def _is_body_value(value: Any) -> bool:
    if isinstance(value, BaseModel):
        return True
    if isinstance(value, list) and value and isinstance(value[0], BaseModel):
        return True
    return False


def _serialize_body(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(exclude_none=True)
    if isinstance(value, list):
        return [v.model_dump(exclude_none=True) if isinstance(v, BaseModel) else v for v in value]
    return value


def _get_return_annotation(fn) -> Any:
    sig = inspect.signature(fn)
    ann = sig.return_annotation
    if ann is inspect.Signature.empty:
        return None
    return ann


def _resolve_return_type(fn, raw_annotation: Any) -> Any:
    """Resolve a possibly-string return annotation to its actual type.

    When `from __future__ import annotations` is in effect, annotations are
    strings; we use `typing.get_type_hints()` to resolve them through the
    function's module globals.
    """
    if raw_annotation is None:
        return None
    if not isinstance(raw_annotation, str):
        return raw_annotation
    try:
        hints = typing.get_type_hints(fn)
        return hints.get("return", raw_annotation)
    except Exception:
        # Fallback: try the function's module globals
        try:
            module = sys.modules.get(getattr(fn, "__module__", None))
            if module is not None:
                return eval(raw_annotation, module.__dict__)  # noqa: S307
        except Exception:
            pass
    return raw_annotation


__all__ = [
    "PaginatedResult",
    "LiveInstance",
    "Resource",
    "BoundResource",
    "GetMixin",
    "ListMixin",
    "CreateMixin",
    "UpdateMixin",
    "DeleteMixin",
    "BoundGetMixin",
    "BoundListMixin",
    "BoundCreateMixin",
    "BoundUpdateMixin",
    "BoundDeleteMixin",
    "ActionMixin",
    "action",
    "stream",
    "sub_resource",
]
