
from pydantic import BaseModel
from typing import Optional, Dict, Any, Union

from acex.models.external_value import ExternalValue
from acex.models.attribute_value import AttributeValue


class SystemConfig(BaseModel):
    contact: Optional[AttributeValue[str]] = None
    domain_name: Optional[AttributeValue[str]] = None
    hostname: Optional[AttributeValue[str]] = None
    location: Optional[AttributeValue[str]] = None

class TripleA(BaseModel): ...
class Logging(BaseModel): ...
class Ntp(BaseModel): ...
class Ssh(BaseModel): ...
class Acl(BaseModel): ...
class Vlans(BaseModel): ...
class Lldp(BaseModel): ...

class Interface(BaseModel): 
    index: AttributeValue[int]
    name: AttributeValue[str]
    enabled: Optional[AttributeValue[bool]] = None
    description: Optional[AttributeValue[str]] = None,
    ipv4: Optional[AttributeValue[str]] = None


class NetworkInstance(BaseModel): ...

class System(BaseModel):
    config: SystemConfig = SystemConfig()
    aaa: Optional[TripleA] = TripleA()
    logging: Optional[Logging] = Logging()
    ntp: Optional[Ntp] = Ntp()
    ssh: Optional[Ssh] = Ssh()

class ComposedConfiguration(BaseModel):
    system: Optional[System] = System()
    acl: Optional[Acl] = Acl()
    vlans: Optional[Vlans] = Vlans()
    lldp: Optional[Lldp] = Lldp()
    interfaces: Dict[str, Interface] = {}
    network_instances: Dict[str, NetworkInstance] = {}
