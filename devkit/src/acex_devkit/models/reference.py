from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel

from acex_devkit.models.container_entry import ContainerEntry


class MetadataValueType(StrEnum):
    CONCRETE = "concrete"
    EXTERNALVALUE = "externalValue"
    REFERENCE = "reference"


class Metadata(BaseModel):
    type: str | None = "str"
    value_source: MetadataValueType = MetadataValueType.CONCRETE


class Reference(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("pointer",)
    pointer: str
    metadata: Metadata = Metadata(type="str", value_source="reference")


class ReferenceTo(Reference):
    pointer: str
    metadata: dict | None = {}


class ReferenceFrom(Reference):
    pointer: str
    metadata: dict | None = {}


class RenderedReference(BaseModel):
    from_ptr: str
    to_ptr: str
