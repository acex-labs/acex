
from acex.configuration.components.base_component import ConfigComponent
from acex.models.attribute_value import AttributeValue

from acex.models.composed_configuration import *


from pydantic import BaseModel
from typing import Any


class SingleAttributeString(BaseModel):
    value: AttributeValue[str]


class HostName(ConfigComponent):
    type = "hostname"
    model_cls = SingleAttributeString

class Contact(ConfigComponent):
    type = "contact"
    model_cls = SingleAttributeString

class Location(ConfigComponent):
    type = "location"
    model_cls = SingleAttributeString

class DomainName(ConfigComponent):
    type = "domain-name"
    model_cls = SingleAttributeString



