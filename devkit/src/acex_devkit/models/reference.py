from pydantic import BaseModel
from typing import Optional, Dict, ClassVar
from enum import Enum

from acex_devkit.models.container_entry import ContainerEntry


class MetadataValueType(str, Enum):
    CONCRETE = "concrete"
    EXTERNALVALUE = "externalValue"
    REFERENCE = "reference"


class Metadata(BaseModel):
    type: Optional[str] = "str"
    value_source: MetadataValueType = MetadataValueType.CONCRETE


class Reference(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("pointer",)
    pointer: str
    metadata: Metadata = Metadata(type="str", value_source="reference")


class ReferenceTo(Reference):
    pointer: str
    metadata: Optional[Dict] = {}


class ReferenceFrom(Reference):
    pointer: str
    metadata: Optional[Dict] = {}


class RenderedReference(BaseModel):
    from_ptr: str
    to_ptr: str
