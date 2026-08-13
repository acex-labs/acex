from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from acex_devkit.models.composed_configuration import ComposedConfiguration


class ConfigComponentField(BaseModel):
    """One field introspected from a ConfigComponent class."""

    name: str
    annotation: str
    default: Any = None


class ConfigComponentCatalogEntry(BaseModel):
    """Catalog row for `GET /config_components/`."""

    type: str
    class_name: str
    module: str
    path_template: str
    fields: list[ConfigComponentField] = []


class NedDriverEntry(BaseModel):
    """Catalog row for `GET /config_components/drivers`."""

    ned_id: str
    name: str
    package_name: str
    version: str
    description: str = ""


class ConfigMapGenerateRequest(BaseModel):
    """Body for `POST /config_components/generate`."""

    components: list[dict[str, Any]]


class ConfigMapGenerateResponse(BaseModel):
    """Result of `POST /config_components/generate`."""

    source: str


class ReconcileMode(StrEnum):
    diff = "diff"
    full = "full"


class ReconcileRequest(BaseModel):
    """Body for `POST /config_components/reconcile/{node_instance_id}`."""

    mode: ReconcileMode = ReconcileMode.diff


class ReconcileResponse(BaseModel):
    """Result of `POST /config_components/reconcile/{node_instance_id}`."""

    configmap: str  # generated Python source


class TranslateRequest(BaseModel):
    """Body for `POST /config_components/translate`."""

    ned_id: str
    config: str
    logical_node_id: int | None = None


class TranslateResponse(BaseModel):
    """Result of `POST /config_components/translate`."""

    configmap: str  # generated Python source
    composed: ComposedConfiguration | None = None
