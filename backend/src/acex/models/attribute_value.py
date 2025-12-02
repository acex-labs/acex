from pydantic import BaseModel, ConfigDict, field_validator, model_validator, field_serializer
from typing import Union, TypeVar, Generic, Optional, Dict, Any, get_args, get_origin
from acex.models.external_value import ExternalValue

T = TypeVar('T')

class AttributeValue(BaseModel, Generic[T]):
    """
    A generic wrapper for values that may be concrete or external.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    value: Union[T, ExternalValue]
    metadata: Optional[Dict[str, Any]] = None

    # ---------------------------------------------------------
    # 1) PRE-PROCESSOR: Tillåt råa värden, ExternalValue direkt,
    #    eller dict → AttributeValue
    # ---------------------------------------------------------
    @model_validator(mode="before")
    @classmethod
    def preprocess_raw(cls, data):
        """
        Gör varje typ av input till en fullvärdig {"value": ...} dict
        så att Pydantic kan fortsätta normalt.
        """
        # 1) Rått värde (str, int, ExternalValue etc)
        if not isinstance(data, dict):
            return {"value": data}

        # 2) Dict som representerar ExternalValue
        if "value" not in data and "ref" in data:
            return {"value": ExternalValue(**data)}

        # 3) Dict som redan har value → låt vara
        return data

    # ---------------------------------------------------------
    # 2) VALIDATOR för value
    # ---------------------------------------------------------
    @field_validator("value", mode="before")
    @classmethod
    def normalize_value(cls, v):
        if isinstance(v, cls):
            return v.value
        if isinstance(v, ExternalValue):
            return v
        if isinstance(v, dict) and "ref" in v:
            return ExternalValue(**v)
        return v

    # ---------------------------------------------------------
    # 3) METADATA-generator (after)
    #    Bevarar redan satt metadata!
    # ---------------------------------------------------------
    @model_validator(mode="after")
    def set_automatic_metadata(self):
        """
        Lägg till metadata utan att ta bort användarens egna.
        """
        self.metadata = dict(self.metadata or {})  # KOPIA – ändra inte originalet

        if isinstance(self.value, ExternalValue):
            self.metadata.setdefault("value_type", "external")
            self.metadata.setdefault("attr_ptr", self.value.attr_ptr)
            self.metadata.setdefault("plugin", self.value.plugin)
            self.metadata.setdefault(
                "ev_type",
                self.value.ev_type.value
                if hasattr(self.value.ev_type, "value")
                else self.value.ev_type,
            )
            self.metadata.setdefault("query", self.value.query)
            self.metadata.setdefault("resolved", self.value.resolved)

            if self.value.kind:
                self.metadata.setdefault("kind", self.value.kind)

            if self.value.resolved and self.value.resolved_at:
                self.metadata.setdefault(
                    "resolved_at",
                    self.value.resolved_at.isoformat()
                    if hasattr(self.value.resolved_at, "isoformat")
                    else str(self.value.resolved_at),
                )

        else:
            self.metadata.setdefault("value_type", "concrete")
            self.metadata.setdefault("type", type(self.value).__name__)

        return self

    # ---------------------------------------------------------
    # 4) SERIALIZER – external value → returnera dess "value"
    # ---------------------------------------------------------
    @field_serializer("value")
    def serialize_value(self, value):
        if isinstance(value, ExternalValue):
            return value.value
        return value

    # Convenience helpers
    def is_external(self) -> bool:
        return isinstance(self.value, ExternalValue)

    def get_value(self) -> T:
        return self.value.value if isinstance(self.value, ExternalValue) else self.value

