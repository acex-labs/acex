"""Refusing a second record for something the inventory already holds.

The services check before they write; the unique indexes on the models hold when two requests race.
Serial numbers and hostnames are compared trimmed and ignoring case (see ``acex.utils.identity``).
"""

import inspect
from contextlib import asynccontextmanager
from dataclasses import dataclass

from acex.models import Asset, LogicalNode, Node
from acex.plugins.integrations import DatabasePlugin
from acex.utils.identity import clean, key_expr
from acex_devkit.models.node_response import AssetRefType
from fastapi import HTTPException
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError


class DuplicateError(HTTPException):
    """409 for a record that already exists. ``detail`` names the field and the record in the way."""

    def __init__(self, resource: str, field: str, value, existing_id, message: str):
        super().__init__(
            status_code=409,
            detail={
                "code": "duplicate",
                "message": message,
                "resource": resource,
                "field": field,
                "value": value,
                "existing_id": existing_id,
            },
        )


@dataclass(frozen=True)
class Unique:
    """One identity kept unique: ``model.field``. ``ci``: case and padding do not count.

    ``also``: columns that must match as well, since an asset and a cluster can have the same id.
    """

    resource: str
    field: str
    model: type
    ci: bool
    message: str
    also: tuple = ()

    def predicate(self, value):
        column = getattr(self.model, self.field)
        same = key_expr(column) == func.lower(value) if self.ci else column == value
        return and_(*(getattr(self.model, name) == fixed for name, fixed in self.also), same)

    def duplicate(self, value, existing_id, subject=None, existing=None) -> DuplicateError:
        """``subject`` names ``value``; ``existing`` names the record in the way."""
        message = self.message.format(
            value=value,
            existing_id=existing_id,
            subject=subject or value,
            existing=existing or f"node instance {existing_id}",
        )
        return DuplicateError(self.resource, self.field, value, existing_id, message)


ASSET_SERIAL = Unique(
    "asset",
    "serial_number",
    Asset,
    True,
    "Asset with serial number '{value}' already exists (id {existing_id}).",
)
LOGICAL_NODE_HOSTNAME = Unique(
    "logical_node",
    "hostname",
    LogicalNode,
    True,
    "Logical node with hostname '{value}' already exists (id {existing_id}).",
)
NODE_LOGICAL_NODE = Unique(
    "node_instance",
    "logical_node_id",
    Node,
    False,
    "Logical node {subject} already has node instance {existing_id}.",
)
# What a node instance runs on, an asset or a cluster, belongs to one node instance.
NODE_ASSET = Unique(
    "node_instance",
    "asset_ref_id",
    Node,
    False,
    "Asset {subject} is already used by {existing}.",
    also=(("asset_ref_type", AssetRefType.asset),),
)
NODE_CLUSTER = Unique(
    "node_instance",
    "asset_ref_id",
    Node,
    False,
    "Cluster {subject} is already used by {existing}.",
    also=(("asset_ref_type", AssetRefType.asset_cluster),),
)


def require_text(value, field: str) -> str:
    """The value without surrounding whitespace; 422, shaped like FastAPI's own, when nothing is left."""
    text = clean(value) if isinstance(value, str) else ""
    if not text:
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["body", field], "msg": f"{field} must not be blank", "type": "value_error"}],
        )
    return text


def as_id(id) -> int | None:
    """The row id behind a path parameter. External plugins may use ids that are not integers."""
    return int(id) if str(id).isdigit() else None


async def _find(adapter, spec: Unique, value, exclude_id: int | None):
    """The record that already holds ``value``, or None."""
    extra_filters = [spec.predicate(value)]
    if exclude_id is not None:
        extra_filters.append(spec.model.id != exclude_id)
    result = adapter.query(filters=None, extra_filters=extra_filters, limit=1)
    if inspect.isawaitable(result):
        result = await result
    items = result["items"]
    return items[0] if items else None


def _name_of(record) -> str | None:
    """The hostname of a node instance's logical node, when the lookup loaded it."""
    logical_node = getattr(record, "logical_node", None)
    return getattr(logical_node, "hostname", None)


@asynccontextmanager
async def unique(adapter, spec: Unique, value, *, exclude_id: int | None = None, skip: bool = False, subject=None):
    """Around a write that is to hold ``value``: ``DuplicateError`` if another record already does.

    When two requests race past the lookup, the unique index fails the second write. It is looked up
    again to tell a duplicate from any other integrity error, which propagates.

    ``skip`` is for an update that leaves the value alone, so a record with a duplicate from before stays
    editable. An external inventory is not checked; it owns its own uniqueness.
    """
    if skip or not isinstance(getattr(adapter, "plugin", None), DatabasePlugin):
        yield
        return

    existing = await _find(adapter, spec, value, exclude_id)
    if existing is not None:
        raise spec.duplicate(value, existing.id, subject, _name_of(existing))
    try:
        yield
    except IntegrityError as exc:
        existing = await _find(adapter, spec, value, exclude_id)
        if existing is None:
            raise
        raise spec.duplicate(value, existing.id, subject, _name_of(existing)) from exc
