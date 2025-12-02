
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Literal, ClassVar
from enum import Enum

from acex.models.external_value import ExternalValue
from acex.models.attribute_value import AttributeValue
from acex.models.logging import (
    LoggingConfig,
    LoggingConsole,
    RemoteServer,
    LoggingEvents
)



class Metadata(BaseModel):
    type: str = "NoneType"


class ReferenceDirection(str, Enum):
    to_self = "to_self"
    from_self = "from_self"


class Reference(BaseModel):
    pointer: str
    direction: ReferenceDirection

class RenderedReference(BaseModel):
    from_ptr: str
    to_ptr: str

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
    metadata: Optional[Metadata] = Metadata()


class Interface(BaseModel): 
    "Base class for all interfaces"
    index: AttributeValue[int]
    name: AttributeValue[str]

    description: Optional[AttributeValue[str]] = None
    enabled: Optional[AttributeValue[bool]] = None
    ipv4: Optional[AttributeValue[str]] = None
    vlan_id: Optional[AttributeValue[int]] = None
    
    metadata: Optional[Metadata] = Field(default_factory=Metadata)
    type: Literal[
        "ethernetCsmacd",
        "ieee8023adLag",
        "l3ipvlan",
        "softwareLoopback",
        "subinterface",
        ] = "ethernetCsmacd"
    
    model_config = {
        "discriminator": "type"
    }

class EthernetCsmacdInterface(Interface):
    "Physical Interface"
    type: Literal["ethernetCsmacd"] = "ethernetCsmacd"

    # Egenskaper för fysiska interface
    subinterfaces: list["SubInterface"] = Field(default_factory=list)
    speed: Optional[AttributeValue[int]] = None
    duplex: Optional[AttributeValue[str]] = None
    switchport_mode: Optional[AttributeValue[Literal["access", "trunk"]]] = None
    trunk_allowed_vlans: Optional[AttributeValue[List[int]]] = None
    native_vlan: Optional[AttributeValue[int]] = None
    voice_vlan: Optional[AttributeValue[int]] = None


class Ieee8023adLagInterface(Interface):
    "LAG Interface"
    type: Literal["ieee8023adLag"] = "ieee8023adLag"
    members: list[str] = Field(default_factory=list)

class L3IpvlanInterface(Interface):
    "SVI Interface"
    type: Literal["l3ipvlan"] = "l3ipvlan"
    vlan_id: Optional[int] = None

class SoftwareLoopbackInterface(Interface):
    "Loopback Interface"
    type: Literal["softwareLoopback"] = "softwareLoopback"

    # Loopback har varken vlan, duplex eller speed
    vlan_id: Optional[int] = None
    ipv4: Optional[AttributeValue[str]] = None

class SubInterface(Interface):
    "Subinterface"
    type: Literal["subinterface"] = "subinterface"

    vlan_id: Optional[int] = None
    ipv4: Optional[AttributeValue[str]] = None


class RouteTarget(BaseModel):
    value: str # TODO: Add constraints and validators... 

class ImportExportPolicy(BaseModel):
    export_route_target: Optional[List[RouteTarget]] = None
    import_route_target: Optional[List[RouteTarget]] = None

class InterInstancePolicy(BaseModel):
    import_export_policy: ImportExportPolicy

class NetworkInstance(BaseModel): 
    name: AttributeValue[str]
    description: Optional[AttributeValue[str]] = None
    vlans: Optional[Dict[str, Vlan]] = {}
    interfaces: Optional[Dict[str, Interface]] = {}
    inter_instance_policies: Optional[Dict[str, InterInstancePolicy]] = {}


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
    network_instances: Dict[str, NetworkInstance] = {"global": NetworkInstance(name="global")}
