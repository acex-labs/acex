
from acex.configuration.components.base_component import ConfigComponent
from acex.models.attribute_value import AttributeValue

from acex.models.composed_configuration import *


class HostName(ConfigComponent):
    type = "hostname"
    model_cls = AttributeValue[str]

class Contact(ConfigComponent):
    type = "contact"
    model_cls = AttributeValue[str]

class Location(ConfigComponent):
    type = "location"
    model_cls = AttributeValue[str]

class DomainName(ConfigComponent):
    type = "domain-name"
    model_cls = AttributeValue[str]

