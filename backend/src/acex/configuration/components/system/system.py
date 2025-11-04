
from acex.configuration.components.base_component import ConfigComponent
from acex.models import SingleAttribute


class SystemAttribute(ConfigComponent): ...

class HostName(SystemAttribute):
    type = "hostname"
    model_cls = SingleAttribute

class Contact(SystemAttribute):
    type = "contact"
    model_cls = SingleAttribute

class Location(SystemAttribute):
    type = "location"
    model_cls = SingleAttribute

class DomainName(SystemAttribute):
    type = "domain-name"
    model_cls = SingleAttribute

