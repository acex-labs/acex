
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Literal, ClassVar, Union, Any
from enum import Enum

from acex.models.external_value import ExternalValue
from acex.models.attribute_value import AttributeValue
from acex.models.logging import (
    LoggingConfig,
    Console,
    RemoteServer,
    VtyLine,
    FileLogging,
    LoggingEvents
)

class MetadataValueType(Enum):
    CONCRETE = "concrete"
    EXTERNALVALUE = "externalValue"
    REFERENCE = "reference"

class Metadata(BaseModel):
    type: Optional[str] = "str"
    value_source: MetadataValueType = MetadataValueType.CONCRETE 

class Reference(BaseModel): 
    pointer: str
    metadata: Metadata = Metadata(type="str", value_source="reference")

class ReferenceTo(Reference):
    pointer: str
    metadata: Optional[Dict] = {}

class ReferenceFrom(Reference):
    pointer: str
    metadata: Optional[Dict] = {}

class RenderedReference(BaseModel):
    from_ptr: str
    to_ptr: str

class SystemConfig(BaseModel):
    contact: Optional[AttributeValue[str]] = None
    domain_name: Optional[AttributeValue[str]] = None
    hostname: Optional[AttributeValue[str]] = None
    location: Optional[AttributeValue[str]] = None

class TripleA(BaseModel): ...

# Trying to avoid using "Logging" or "logging" as names for anything due to conflicts with standard lib.
class LoggingComponents(BaseModel): 
    config: LoggingConfig = LoggingConfig()
    console: Optional[Console] = None
    remote_servers: Optional[Dict[str, RemoteServer]] = {}
    events: Optional[LoggingEvents] = None
    vty: Optional[Dict[str, VtyLine]] = {}
    files: Optional[Dict[str, FileLogging]] = {}

class NtpConfig(BaseModel):
    enabled: AttributeValue[bool] = False

class NtpServer(BaseModel):
    address: AttributeValue[str]
    port: Optional[AttributeValue[int]] = None
    version: Optional[AttributeValue[int]] = None
    association_typ: Optional[AttributeValue[str]] = None
    prefer: Optional[AttributeValue[bool]] = None
    source_interface: Optional[AttributeValue[str]] = None

class Ntp(BaseModel): 
    config: Optional[NtpConfig] = NtpConfig()
    servers: Optional[Dict[str, NtpServer]] = {}

class SshServer(BaseModel): 
    enable: Optional[AttributeValue[bool]] = None
    protocol_version: Optional[AttributeValue[int]] = 2
    timeout: Optional[AttributeValue[int]] = None
    auth_retries: Optional[AttributeValue[int]] = None
    source_interface: Optional[Reference] = None

class AuthorizedKeyAlgorithms(str, Enum):
    SSH_ED25519 = "ssh-ed25519"
    ECDSA_NISTP256 = "ecdsa-sha2-nistp256"
    ECDSA_NISTP384 = "ecdsa-sha2-nistp384"
    ECDSA_NISTP521 = "ecdsa-sha2-nistp521"
    RSA_SHA2_256 = "rsa-sha2-256"
    RSA_SHA2_512 = "rsa-sha2-512"
    SK_SSH_ED25519 = "sk-ssh-ed25519@openssh.com"
    SK_ECDSA_NISTP256 = "sk-ecdsa-sha2-nistp256@openssh.com"
    SSH_RSA = "ssh-rsa"
    SSH_DSS = "ssh-dss"

class AuthorizedKey(BaseModel):
    algorithm: AuthorizedKeyAlgorithms
    public_key: str

class Ssh(BaseModel): 
    config: Optional[SshServer] = None
    host_keys: Optional[Dict[str, AuthorizedKey]] = {}

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
    
    metadata: Optional[Metadata] = Metadata()
    type: Literal[
        "ethernetCsmacd",
        "ieee8023adLag",
        "l3ipvlan",
        "softwareLoopback",
        "subinterface",
        "managementInterface"
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
    switchport: Optional[AttributeValue[bool]] = None
    switchport_mode: Optional[AttributeValue[Literal["access", "trunk"]]] = None
    trunk_allowed_vlans: Optional[AttributeValue[List[int]]] = None
    native_vlan: Optional[AttributeValue[int]] = None
    access_vlan: Optional[AttributeValue[int]] = None
    vlan_id: Optional[AttributeValue[int]] = None
    voice_vlan: Optional[AttributeValue[int]] = None
    mtu: Optional[AttributeValue[int]] = None # No default set as it differs between devices and vendors

    # LACP relaterade attribut
    aggregate_id: Optional[AttributeValue[int]] = None
    lacp_enabled: Optional[AttributeValue[bool]] = None
    lacp_mode: Optional[AttributeValue[Literal["active", "passive", "on", "auto"]]] = None
    lacp_port_priority: Optional[AttributeValue[int]] = None
    #lacp_system_id_mac: Optional[AttributeValue[str]] = None
    lacp_interval: Optional[AttributeValue[Literal["fast", "slow"]]] = None

class Ieee8023adLagInterface(Interface):
    "LAG Interface"
    type: Literal["ieee8023adLag"] = "ieee8023adLag"
    #aggregate_id: AttributeValue[int] = None
    aggregate_id: int = None
    members: list[str] = Field(default_factory=list)
    max_ports: Optional[AttributeValue[int]] = None
    switchport: Optional[AttributeValue[bool]] = None
    switchport_mode: Optional[AttributeValue[Literal["access", "trunk"]]] = None
    trunk_allowed_vlans: Optional[AttributeValue[List[int]]] = None
    native_vlan: Optional[AttributeValue[int]] = None
    mtu: Optional[AttributeValue[int]] = None # No default set as it differs between devices and vendors

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

class ManagementInterface(Interface):
    "Management Interface"
    type: Literal["managementInterface"] = "managementInterface"

    # Mgmt har inte vlan
    vlan_id: Optional[int] = None

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
    interfaces: Optional[Dict[str, Reference]] = {}
    inter_instance_policies: Optional[Dict[str, InterInstancePolicy]] = {}

class LacpConfig(BaseModel):
    system_priority: Optional[AttributeValue[int]] = None
    system_id_mac: Optional[AttributeValue[str]] = None
    load_balance_algorithm: Optional[AttributeValue[list[Literal["src-mac", "dst-mac", "src-dst-mac", "src-ip", "dst-ip", "src-dst-ip", "src-port", "dst-port", "src-dst-port"]]]] = None

class Lacp(BaseModel):
    config: Optional[LacpConfig] = LacpConfig()
    interfaces: Optional[Dict[str, Interface]] = {}

class System(BaseModel):
    config: SystemConfig = SystemConfig()
    aaa: Optional[TripleA] = TripleA()
    logging: Optional[LoggingComponents] = LoggingComponents() # Trying to avoid using "Logging" or "logging" as names for anything due to conflicts with standard lib.
    ntp: Optional[Ntp] = Ntp()
    ssh: Optional[Ssh] = Ssh()


# For different types of interfaces that are fine for response model:
InterfaceType = Union[
    EthernetCsmacdInterface,
    Ieee8023adLagInterface,
    L3IpvlanInterface,
    SoftwareLoopbackInterface,
    SubInterface,
    ManagementInterface,
]

class ComposedConfiguration(BaseModel):
    system: Optional[System] = System()
    acl: Optional[Acl] = Acl()
    lldp: Optional[Lldp] = Lldp()
    lacp: Optional[Lacp] = Lacp()
    interfaces: Dict[str, InterfaceType] = {}
    network_instances: Dict[str, NetworkInstance] = {"global": NetworkInstance(name="global")}