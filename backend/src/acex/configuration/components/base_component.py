from collections import defaultdict
from ipaddress import IPv4Interface, IPv6Interface, IPv4Address
from pydantic import BaseModel
import json, hashlib
from typing import Dict, Any, Type, Union, Optional, get_origin
from types import NoneType
from datetime import datetime
from acex.models import ExternalValue, AttributeValue


class ConfigComponent:
    type: str = "component"
    name: str = None
    model_cls: Type[BaseModel] = None

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

        # Hook for preprocessing kwargs before initialization
        if hasattr(self, "pre_init"):
            getattr(self, "pre_init")()

        # Validate against the model for the component type
        self.model = self._validate_model(self.kwargs)

        # Set name for component, must always be unique.
        # For single attribute values, name is same as the single positional arg.
        self._set_name_attribute()


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

