from pydantic import BaseModel, ConfigDict, field_validator, field_serializer, PrivateAttr
from sqlmodel import SQLModel, Field
from typing import Literal, Callable, Optional, Any
from datetime import datetime, timezone
from enum import Enum


class EVType(Enum):
    data = "data"
    resource = "resource"

class ExternalValue(SQLModel, table=True):
    ref: str = Field(default=None, primary_key=True)
    
    # query: dict # same query as was used for fetching the data
    query: str = '{"json_query": "in_stringformat"}'
    value: Optional[str] = None
    kind: str # object kind/type
    ev_type: EVType = Field(default=EVType.data)
    plugin: str
    resolved_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    
    # Privat attribut för callable (inte i JSON eller databas)
    _callable: Optional[Callable] = PrivateAttr(default=None)
    
    @field_validator('ev_type', mode='before')
    @classmethod
    def validate_ev_type(cls, v):
        if isinstance(v, str):
            return EVType(v)
        return v

    @field_serializer('ev_type')
    def serialize_ev_type(self, value) -> str:
        if isinstance(value, EVType):
            return value.value
        if isinstance(value, str):
            return value
        return str(value)

