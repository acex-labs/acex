from collections.abc import Callable
from datetime import datetime
from enum import Enum

from pydantic import ConfigDict, PrivateAttr, field_serializer, field_validator
from sqlmodel import Field, SQLModel


class EVType(Enum):
    data = "data"
    resource = "resource"


class ExternalValue(SQLModel, table=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    attr_ptr: str = Field(default=None, primary_key=True)

    # query: dict # same query as was used for fetching the data
    query: str = '{"json_query": "in_stringformat"}'
    value: str | None = None
    kind: str  # object kind/type
    ev_type: EVType = Field(default=EVType.data)
    plugin: str
    resolved: bool = Field(default=False)  # True when value has been resolved
    resolved_at: datetime | None = Field(default=None)  # Only set when resolved

    # Privat attribut för callable (inte i JSON eller databas)
    _callable: Callable | None = PrivateAttr(default=None)

    @field_validator("ev_type", mode="before")
    @classmethod
    def validate_ev_type(cls, v):
        if isinstance(v, str):
            return EVType(v)
        return v

    @field_serializer("ev_type")
    def serialize_ev_type(self, value) -> str:
        if isinstance(value, EVType):
            return value.value
        if isinstance(value, str):
            return value
        return str(value)
