from collections import defaultdict
from ipaddress import IPv4Interface, IPv6Interface, IPv4Address
from pydantic import BaseModel
import json, hashlib
from typing import ClassVar, Dict, Any, Type, Union, Optional, get_origin, TYPE_CHECKING, List
from types import NoneType
from datetime import datetime
from acex_devkit.models import ExternalValue, AttributeValue

if TYPE_CHECKING:
    from acex.observability.components.base import TelemetryComponent


def _annotation_includes(annotation, target_type) -> bool:
    """Return True if target_type appears anywhere in a (possibly generic) annotation."""
    if annotation is target_type:
        return True
    args = getattr(annotation, "__args__", None)
    if args:
        return any(_annotation_includes(a, target_type) for a in args)
    return False


def _coerce_reference(val, ref_type):
    """Convert a ConfigComponent instance (or string/list/dict thereof) to ReferenceTo."""
    from acex_devkit.models.composed_configuration import ReferenceTo

    def _single(v):
        if v is None or isinstance(v, ReferenceTo):
            return v
        if isinstance(v, str):
            from acex.configuration.configuration import Configuration
            from string import Template
            path = Configuration.COMPONENT_MAPPING.get(ref_type)
            if path and not isinstance(path, Template):
                return ReferenceTo(pointer=f"{path}.{v}")
            return ReferenceTo(pointer=v)
        # Augment instance — path is target_path + augments slot
        from acex.configuration.components.augments.base import Augment
        if isinstance(v, Augment):
            return ReferenceTo(pointer=f"{v._target_path}.augments.{v.type}")
        # Regular ConfigComponent — walk MRO to find a non-Template path
        if isinstance(v, ConfigComponent):
            from acex.configuration.configuration import Configuration
            from string import Template
            for cls in type(v).__mro__:
                path = Configuration.COMPONENT_MAPPING.get(cls)
                if path is not None and not isinstance(path, Template):
                    return ReferenceTo(pointer=f"{path}.{v.name}")
        raise ValueError(f"Cannot resolve reference path for {type(v).__name__}")

    if isinstance(val, list):
        return {(item.name if item.name is not None else item.type): _single(item) for item in val}
    if isinstance(val, dict):
        return {k: _single(v) for k, v in val.items()}
    return _single(val)


class ConfigComponent:
    type: str = "component"
    name: str = None
    model_cls: Type[BaseModel] = None
    references: ClassVar[dict] = {}  # {field_name: ComponentType}

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

        # Hook for preprocessing kwargs before initialization
        if hasattr(self, "pre_init"):
            getattr(self, "pre_init")()

        self._resolve_references()

        # Validate against the model for the component type
        self.model = self._validate_model(self.kwargs)

        # Set name for component, must always be unique.
        # For single attribute values, name is same as the single positional arg.
        self._set_name_attribute()

    def _resolve_references(self):
        from acex_devkit.models.composed_configuration import ReferenceTo
        # Explicit declarations
        for field, ref_type in self.__class__.references.items():
            if field in self.kwargs:
                self.kwargs[field] = _coerce_reference(self.kwargs[field], ref_type)
        # Auto-detect: fält vars modell-typ innehåller ReferenceTo
        model_cls = self.__class__.model_cls
        if model_cls:
            for field, info in model_cls.model_fields.items():
                if field in self.kwargs and field not in self.__class__.references:
                    if _annotation_includes(info.annotation, ReferenceTo):
                        self.kwargs[field] = _coerce_reference(self.kwargs[field], None)

    def telemetry(self) -> List["TelemetryComponent"]:
        """
        Default observability hook — return TelemetryComponents derived from
        this config component (e.g. BgpNeighbor → BgpNeighborTelemetry).

        Default is empty. Override in components that have operational state
        worth collecting (mirrors YANG `config false` siblings).
        """
        return []


    def _validate_model(self, kwargs) -> BaseModel:
        """
        Validate all kwargs against the model and set attribute
        types accordingly
        """
        if not self.__class__.model_cls:
            raise ValueError(f"No model_cls defined for {self.__class__.__name__}")
        try:
            # Create an instance of the model class with kwargs
            model_instance = self.__class__.model_cls(**kwargs)
            return model_instance
        except Exception as e:
            raise ValueError(f"Failed to validate kwargs against model {self.__class__.model_cls.__name__}: {e}")


    def _set_name_attribute(self):
        """
        Set name attribute to component, not included in the model
        but will have to be unique for mapping/dict-key in the composite configuration.

        # If self.model is AttributeValue[str], that means its a "single-attr 
        component which has no requirement for name, since it can only be one 
        of them in the config. So its name is same as the class name.
        """
        if isinstance(self.model, AttributeValue[str]):
            self.name = self.__class__.__name__.lower()
        else:
            self.name = self.kwargs.get("name")

