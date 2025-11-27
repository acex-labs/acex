
from pydantic import BaseModel
from typing import Optional, Dict, Any, Union

from acex.models.external_value import ExternalValue
from acex.models.attribute_value import AttributeValue


from acex.models.logging import (
    LoggingConfig,
    LoggingConsole,
    RemoteServer,
    LoggingEvents
)

class SystemConfig(BaseModel):
    contact: Optional[AttributeValue[str]] = None
    domain_name: Optional[AttributeValue[str]] = None
    hostname: Optional[AttributeValue[str]] = None
    location: Optional[AttributeValue[str]] = None

class TripleA(BaseModel): ...


class Logging(BaseModel): 
    config: LoggingConfig = LoggingConfig()
    console: Optional[LoggingConsole] = None
    remote_servers: Optional[RemoteServer] = None
    events: Optional[LoggingEvents] = None


class Ntp(BaseModel): ...
class Ssh(BaseModel): ...
class Acl(BaseModel): ...
class Lldp(BaseModel): ...


class Vlan(BaseModel):
    name: AttributeValue[str]
    vlan_id: Optional[AttributeValue[int]] = None
    vlan_name: Optional[AttributeValue[str]] = None
    network_instance: Optional[AttributeValue[str]] = None


class Interface(BaseModel): 
    index: AttributeValue[int]
    name: AttributeValue[str]
    enabled: Optional[AttributeValue[bool]] = None
    description: Optional[AttributeValue[str]] = None
    ipv4: Optional[AttributeValue[str]] = None
    network_instance: Optional[AttributeValue[str]] = None


class SubInterface(Interface): ...


class PhysicalInterface(Interface): ...


class NetworkInstance(BaseModel): 
    vlans: Optional[Dict[str, Vlan]] = None
    interfaces: Optional[Dict[str, Interface]] = None

class System(BaseModel):
    config: SystemConfig = SystemConfig()
    aaa: Optional[TripleA] = TripleA()
    logging: Optional[Logging] = Logging()
    ntp: Optional[Ntp] = Ntp()
    ssh: Optional[Ssh] = Ssh()

class ComposedConfiguration(BaseModel):
    system: Optional[System] = System()
    acl: Optional[Acl] = Acl()
    lldp: Optional[Lldp] = Lldp()
    interfaces: Dict[str, Interface] = {}
    network_instances: Dict[str, NetworkInstance] = {"global": {"vlans": {}, "interfaces": {}}}
