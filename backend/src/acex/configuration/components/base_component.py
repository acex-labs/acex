from collections import defaultdict
from ipaddress import IPv4Interface, IPv6Interface, IPv4Address
from pydantic import BaseModel
import json, hashlib
from typing import Dict, Any, Type, Union, Optional, get_origin
from types import NoneType
from datetime import datetime
from acex.models import ExternalValue, SingleAttribute

"""
FIXA!

just nu wrappas även containers som AttributeValue, det är ju bara själva attributen som ska vara det.
Tex wrappas hela Interface som attributevalue, det är bara attributen på komponenterna som ska vara det. 

fixa det.

"""

class AttributeValue:
    """
    Simple wrapper for attributes to store in consistent format
    Each attribute of each ConfigComponent consists of:
     - type: str (concrete|externalValue)
     - value: str
     - _meta: dict
    """
    
    def __init__(self, data: Union[Any, ExternalValue, None] = None):
        self.data = data
    
    @property
    def value(self) -> str:
        if isinstance(self.data, (str, int, bool)):
            return self.data
        elif isinstance(self.data, ExternalValue):
            return self.data.value
        elif isinstance(self.data, IPv4Address):
            return str(self.data)
        else:
            return "Whoah! this was unexpected.."

    @value.setter
    def value(self, value):
        self.data.value = value

    @property
    def type(self) -> str:
        return self._get_type_repr()

    @property
    def meta(self) -> dict:
        return self._get_meta_repr()

    def to_json(self) -> dict:
        res = {
            "type": self.type,
            "value": self.value,
        }
        if self.meta is not None:
            res["_meta"] = self.meta

        return res

    def _get_type_repr(self) -> str:
        """
        Return self.type as a more informational representation
        """
        if isinstance(self.data, ExternalValue):
            return "externalValue"
        else:
            return "concrete" # Visar att attributet är satt specifikt i configMap.

    def _get_meta_repr(self):
        if self.type == "concrete":
           return None # No meta is necessary yet.
        elif self.type == "externalValue":
            return {
                "ref": self.data.ref,
                "query": self.data.query,
                "kind": self.data.kind,
                "ev_type": self.data.ev_type,
                "plugin": self.data.plugin,
                "resolved_at": self.data.resolved_at
            }
        else:
            return {"msg": "This is unexpected, let someone know plz"}


class ConfigComponent:
    type: str = "component"
    model_cls: Type[BaseModel] = None

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        
        # This is where we store the config for the component itself.
        self.config = {}

        # Ff the component is a parent of a composition, it may hold 'children'
        # Compositions are defined as annotations to the configComponent class
        self.children = defaultdict(dict)

        # Hook for preprocessing kwargs before initialization
        # Pass kwargs dict directly (not unpacked) so modifications happen by reference
        if hasattr(self, "pre_init"):
            getattr(self, "pre_init")()

        # Extra children can be added by annontations to the ConfigComponent
        annotations = self.__class__.__annotations__
        if annotations != {}:
            # print(f"ConfigComponent {self.__class__} is annotated with: {", ".join(annotations.keys())}")
            for k, v in annotations.items():
                annotation_type = get_origin(annotations[k])

                # Use value from config map if set, otherwise use empty default type based on annotation.
                if kwargs.get(k) is not None:
                    self.children[k] = kwargs.get(k) # Must be valid ConfigComponents with .to_json() methods
                else:
                    # If no value is added, use new instance based on annotation
                    self.children[k] = annotation_type()

        # Check all values against the model
        self.model = self._validate_model(kwargs)

        # For singleattribute components:
        # - key is same as component classname
        # - value is first argument from init
        if isinstance(self.model, SingleAttribute):
            self._key = "value"
            value = args[0]
            self.config[self._key] = AttributeValue(value)
        else:
            self._key = kwargs["name"] # Todo: lägg till felhantering i de fall ett objekt inte är singled attribute men saknar name.

            for field_name in self.model.model_fields.keys():
                value = getattr(self.model, field_name)
                if value is not None:
                    self.config[field_name] = AttributeValue(value)

    @property
    def path(self):
        return f"{self.type}.{self._key}"


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


    def attributes(self):
        """Get all AttributeValue attributes from config"""
        attributes = {}

        for k,v in self.config.items():
            attributes[k] = v

        return attributes

    def to_json(self):
        """Serialize to JSON with consistent structure."""
        result = {
            "name": self.path,
            "type": self.type,
            "config": {}, # This is where item values is placed
            "_meta": {} # this is where stuff like external value ref etc is placed
        }
        for k, v in self.attributes().items():
            # Skip 'name' since it's already in the outer structure as "name": self.path
            # Only include attributes that have actual values (not None)
            if k not in ("type", "name", "config") and v.data is not None:
                result["config"][k] = v.to_json()
        
        # Add children (like vlans) to the result
        for k, v in self.children.items():
            result[k] = v.to_json()
        
        return result


    def __repr__(self):
        return f"<{self.__class__.__name__}_pk=key>"

