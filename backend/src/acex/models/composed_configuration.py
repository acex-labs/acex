
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
from acex.models.spanning_tree import SpanningTree

class MetadataValueType(str, Enum):
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
    stack_index: Optional[AttributeValue[int]] = None
    module_index: Optional[AttributeValue[int]] = None
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

    # Spanning-tree relaterade attribut
    stp_port_priority: Optional[int] = None
    stp_cost: Optional[int] = None
    stp_edge_port: Optional[bool] = False # Disabled by default
    stp_bpdu_filter: Optional[bool] = False # Disabled by default
    stp_bpdu_guard: Optional[bool] = False # Disabled by default
    stp_loop_guard: Optional[bool] = False # Disabled by default
    stp_root_guard: Optional[bool] = False # Disabled by default
    stp_portfast: Optional[bool] = False # Disabled by default
    stp_link_type: Optional[Literal["point-to-point", "shared"]] = None  # e.g., "point-to-point", "shared"


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

# SNMP
class SnmpAccess(str, Enum):
	READ_ONLY = "READ_ONLY"
	READ_WRITE = "READ_WRITE"


class SnmpSecurityLevel(str, Enum):
	NO_AUTH_NO_PRIV = "NO_AUTH_NO_PRIV"
	AUTH_NO_PRIV = "AUTH_NO_PRIV"
	AUTH_PRIV = "AUTH_PRIV"


class SnmpAuthProtocol(str, Enum):
	MD5 = "MD5"
	SHA1 = "SHA"
	SHA224 = "SHA-224"
	SHA256 = "SHA-256"
	SHA384 = "SHA-384"
	SHA512 = "SHA-512"


class SnmpPrivProtocol(str, Enum):
	DES = "DES"
	TRIPLE_DES = "3DES"
	AES128 = "AES128"
	AES192 = "AES192"
	AES256 = "AES256"


class SnmpConfig(BaseModel):
	enabled: AttributeValue[bool] = False
	engine_id: Optional[AttributeValue[str]] = None
	location: Optional[AttributeValue[str]] = None
	contact: Optional[AttributeValue[str]] = None


class SnmpCommunity(BaseModel):
    name: AttributeValue[str]
    community: Optional[AttributeValue[str]] = None # Community string
    access: Optional[AttributeValue[SnmpAccess]] = SnmpAccess.READ_ONLY
    view: Optional[AttributeValue[str]] = None
    ipv4_acl: Optional[AttributeValue[str]] = None # Cisco and "liknande" vendors 
    ipv6_acl: Optional[AttributeValue[str]] = None
    source_interface: Optional[Reference] = None
    clients: Optional[AttributeValue[List[str]]] = None # Juniper specific


class SnmpUser(BaseModel):
	username: AttributeValue[str]
	security_level: Optional[AttributeValue[SnmpSecurityLevel]] = SnmpSecurityLevel.NO_AUTH_NO_PRIV
	auth_protocol: Optional[AttributeValue[SnmpAuthProtocol]] = None
	auth_password: Optional[AttributeValue[str]] = None
	priv_protocol: Optional[AttributeValue[SnmpPrivProtocol]] = None
	priv_password: Optional[AttributeValue[str]] = None


class SnmpView(BaseModel):
	name: AttributeValue[str]
	oid: AttributeValue[str]
	included: Optional[AttributeValue[bool]] = True


class SnmpServer(BaseModel):
    name: str
    address: AttributeValue[str]
    port: Optional[AttributeValue[int]] = 162
    enabled: Optional[AttributeValue[bool]] = True
    version: Optional[AttributeValue[Literal["v2c", "v3"]]] = None
    community: Optional[AttributeValue[str]] = None
    username: Optional[AttributeValue[str]] = None
    security_level: Optional[AttributeValue[SnmpSecurityLevel]] = None
    source_interface: Optional[Reference] = None
    network_instance: Optional[AttributeValue[str]] = None

# ----------------------------
# Enum-based trap groups
# ----------------------------
# En stor class med Enum	
class TrapEventOptions(str, Enum):
	VRF_UP = "vrf-up"
	VRF_DOWN = "vrf-down"
	VNET_TRUNK_UP = "vnet-trunk-up"
	VNET_TRUNK_DOWN = "vnet-trunk-down"
	ALL = "all"
	RfEvent = 'enabled'
	VlanMembershipEvent = 'enabled'
	ErrdisableEvent = 'enabled'
	CHANGE = "change"
	MOVE = "move"
	THRESHOLD = "threshold"
	AUTHENTICATION = "authentication"
	LINKDOWN = "linkdown"
	LINKUP = "linkup"
	COLDSTART = "coldstart"
	WARMSTART = "warmstart"
	FLOWMONEVENT = "trapflowmonevent"
	ENTITYPERFEVENT = "trapentityperfevent"
	PCALLHOMEEVENT_MESSAGE_SEND_FAIL = "trapcallhomeevent_MESSAGE_SEND_FAIL"
	CALLHOMEEVENT_SERVER_FAIL = "trapcallhomeevent_SERVER_FAIL"	
	TTYEVENT = "trapttyevent"
	EIGRPEVENT = "trapeigrpevent"
	OSPF_STATE_CHANGE = "ospf_state_change"
	OSPF_ERRORS = "ospf_errors"
	OSPF_RETRANSMIT = "ospf_retransmit"
	OSPF_LSA = "ospf_lsa"
	OSPF_CISCO_TRANS_CHANGE = "ospf_cisco_trans_change"
	OSPF_CISCO_SHAMLINK_INTERFACE = "ospf_cisco_shamlink_interface"
	OSPF_CISCO_SHAMLINK_NEIGHBOR = "ospf_cisco_shamlink_neighbor"
	BFD_EVENT = "bfd_event"
	CISCO_SMART_LICENSE_EVENT = "cisco_smart_license_event"
	AUTH_FRAMEWORK_SEC_VIOLATION = "auth_framework_sec_violation"
	REP_EVENT = "rep_event"
	MEMORY_BUFFERPEAK = "memory_bufferpeak"
	CONFIG_COPY = "config_copy"
	CONFIG = "config"
	CONFIG_CTID = "config_ctid"
	ENERGYWISE_EVENT = "energy_wise_event"
	FRU_CTRL_EVENT = "fru_ctrl_event"
	ENTITY_EVENT = "entity_event"
	FLASH_INSERTION = "flash_insertion"
	FLASH_REMOVAL = "flash_removal"
	FLASH_LOWSPACE = "flash_lowspace"
	POWER_ETHERNET_POLICE = "power_ethernet_police"
	POWER_ETHERNET_GROUP_THRESHOLD = "power_ethernet_group_threshold"
	CPU_THRESHOLD = "cpu_threshold"
	SYSLOG = "syslog"
	UDLD_LINK_FAIL_RPT = "udld_link_fail_rpt"
	UDLD_STATUS_CHANGE = "udld_status_change"
	VTP_EVENT = "vtp_event"
	VLAN_CREATE = "vlancreate"
	VLAN_DELETE = "vlandelete"
	PORT_SECURITY = "port_security"
	ENV_MON = "env_mon"
	STACKWISE = "stackwise"
	MVPN = "mvpn"
	PW_VC = "pw_vc"	
	IPSLA = "ipsla"
	DHCP = "dhcp"
	EVENT_MANAGER = "event_manager"
	IKE_POLICY_ADD = "ike_policy_add"
	IKE_POLICY_DELETE = "ike_policy_delete"
	IKE_TUNNEL_START = "ike_tunnel_start"
	IKE_TUNNEL_STOP = "ike_tunnel_stop"
	IPSEC_CRYPTOMAP_ADD = "ipsec_cryptomap_add"
	IPSEC_CRYPTOMAP_DELETE = "ipsec_cryptomap_delete"
	IPSEC_CRYPTOMAP_ATTACH = "ipsec_cryptomap_attach"
	IPSEC_CRYPTOMAP_DETACH = "ipsec_cryptomap_detach"
	IPSEC_TUNNEL_START = "ipsec_tunnel_start"
	IPSEC_TUNNEL_STOP = "ipsec_tunnel_stop"
	IPSEC_TOO_MANY_SAS = "ipsec_too_many_sas"
	OSPFV3_STATE_CHANGE = "ospfv3_state_change"
	OSPFV3_ERRORS = "ospfv3_errors"
	IP_MULTICAST = "ip_multicast"
	MSDP = "msdp"
	PIM_NEIGHBOR_CHANGE = "pim_neighbor_change"
	PIM_RP_MAPPING_CHANGE = "pim_rp_mapping_change"
	INVALID_PIM_MESSAGE = "invalid_pim_message"
	BRIDGE_NEWROOT = "bridge_newroot"
	BRIDGE_TOPOLOGYCHANGE = "bridge_topologychange"
	STPX_INCONSISTENCY = "stpx_inconsistency"
	STPX_ROOT_INCONSISTENCY = "stpx_root_inconsistency"
	STPX_LOOP_INCONSISTENCY = "stpx_loop_inconsistency"
	BGP_CBG2 = "bgp_cbg2"
	HSRP = "hsrp"
	ISIS = "isis"
	CEF_RESOURCE_FAILURE = "cef_resource_failure"
	CEF_PEER_STATE_CHANGE = "cef_peer_state_change"
	CEF_PEER_FIB_STATE_CHANGE = "cef_peer_fib_state_change"
	CEF_INCONSISTENCY = "cef_inconsistency"
	LISP = "lisp"
	NHRP_NHS = "nhrp_nhs"
	NHRP_NHC = "nhrp_nhc"
	NHRP_NHP = "nhrp_nhp"
	NHRP_QUOTA_EXCEEDED = "nhrp_quota_exceeded"
	LOCAL_AUTH = "local_auth"
	ENTITY_DIAG_BOOT_UP_FAIL = "entity_diag_boot_up_fail"
	ENTITY_DIAG_HM_TEST_RECOVER = "entity_diag_hm_test_recover"
	ENTITY_DIAG_HM_THRESH_REACHED = "entity_diag_hm_thresh_reached"
	ENTITY_DIAG_SCHEDULED_TEST_FAIL = "entity_diag_scheduled_test_fail"
	MPLS_RFC_LDP = "mpls_rfc_ldp"
	MPLS_LDP = "mpls_ldp"
	MPLS_RFC_TRAFFIC_ENG = "mpls_rfc_traffic_eng"
	MPLS_TRAFFIC_ENG = "mpls_traffic_eng"
	MPLS_FAST_REROUTE_PROTECTED = "mpls_fast_reroute_protected"
	MPLS_VPN = "mpls_vpn"
	MPLS_RFC_VPN = "mpls_rfc_vpn"
	BULKSTAT_COLLECTION = "bulkstat_collection"
	BULKSTAT_TRANSFER = "bulkstat_transfer"

class TrapEvent(BaseModel):
    name: str
    event_name: TrapEventOptions

#class SnmpTrap(BaseModel): ...

class Snmp(BaseModel):
    config: SnmpConfig = SnmpConfig()
    communities: Optional[Dict[str, SnmpCommunity]] = {}
    users: Optional[Dict[str, SnmpUser]] = {}
    trap_servers: Optional[Dict[str, SnmpServer]] = {}
    trap_events: Optional[Dict[str, TrapEvent]] = {}
    views: Optional[Dict[str, SnmpView]] = {}

# AAA
class aaaBaseClass(BaseModel):
    name: str = None

class aaaTacacsAttributes(aaaBaseClass):
    port: Optional[int] = 49
    secret_key: Optional[str] = None
    secret_key_hashed: Optional[str] = None
    address: Optional[str] = None
    timeout: Optional[int] = 30
    source_address: Optional[str] = None #Optional[Reference] = None # should be reference

class aaaRadiusAttributes(aaaBaseClass):
    auth_port: Optional[int] = 1812
    acct_port: Optional[int] = 1813
    secret_key: Optional[str] = None
    secret_key_hashed: Optional[str] = None
    address: Optional[str] = None
    timeout: Optional[int] = 30
    source_address: Optional[str] = None #Optional[Reference] = None # should be reference
    retransmit_attempts: Optional[int] = 3

class aaaServerGroupAttributes(BaseModel):
    enable: Optional[bool] = False
    type: Optional[Literal['tacacs','radius']] = None
    #servers: Optional[list] = None 
    #address: Optional[str] = None 
    #timeout: Optional[int] = 30
    tacacs: Optional[Reference] = None
    radius: Optional[Reference] = None

# Authentication Models
class aaaAuthenticationMethods(aaaBaseClass):
    method: Optional[List[str]] = None # Ex. ['TACACS_GROUP','LOCAL'], TACACS_GROUP is reference to server group

class authenticationUser(aaaBaseClass):
    username: Optional[str] = None
    password: Optional[str] = None
    password_hahsed: Optional[str] = None
    ssh_key: Optional[str] = None
    role: Optional[str] = None

class aaaAuthenticationUsers(aaaBaseClass):
    username: Optional[Dict[str, authenticationUser]] = {}

class adminUser(aaaBaseClass): # when to use this?
    admin_password: Optional[str] = None
    admin_password_hashed: Optional[str] = None

class aaaAuthenticationAdminUsers(BaseModel):
    config: Optional[Dict[str, adminUser]] = {}

class aaaAuthentication(BaseModel):
    config: Optional[Dict[str, aaaAuthenticationMethods]] = {}
    admin_user: Optional[Dict[str, aaaAuthenticationAdminUsers]] = {}
    users: Optional[Dict[str, aaaAuthenticationUsers]] = {}

# Authorization Models
class aaaAuthorizationMethods(aaaBaseClass):
    method: Optional[List[str]] = None # Ex. ['TACACS_GROUP','LOCAL']

class aaaAuthorizationEvent(aaaBaseClass):
    event_type: dict = {
        'event-type':'command',
        'method':['tacacs_group']
    }

class aaaAuthorizationEvents(BaseModel):
    event: Optional[Dict[str, aaaAuthorizationEvent]] = {}

class aaaAuthorization(BaseModel):
    config: Optional[Dict[str, aaaAuthorizationMethods]] = {}
    events: Optional[Dict[str, aaaAuthorizationEvents]] = {}

# Accounting Models
class aaaAccountingMethods(BaseModel):
    method: Optional[List[str]] = None # Ex. ['TACACS_GROUP','LOCAL']

class aaaAccountingEvents(BaseModel):
    event: list = [
        {
        'event-type': 'command',
        'config': {
            'event-type': 'command',
            'method': ['tacacs_group']
            }
        },
        {
        'event-type': 'system',
        'config': {
            'event-type': 'system',
            'method': ['tacacs_group']
            }
        }
    ]

class aaaAccounting(BaseModel):
    config: aaaAccountingMethods = aaaAccountingMethods()
    events: aaaAccountingEvents = aaaAccountingEvents()

class TripleA(BaseModel):
    #config: dict = None
    server_groups: Optional[Dict[str, aaaServerGroupAttributes]] = {}
    tacacs: Optional[Dict[str, aaaTacacsAttributes]] = {}
    radius: Optional[Dict[str, aaaRadiusAttributes]] = {}
    authentication: aaaAuthentication = aaaAuthentication()
    authorization: aaaAuthorization = aaaAuthorization()
    accounting: aaaAccounting = aaaAccounting()

class System(BaseModel):
    config: SystemConfig = SystemConfig()
    aaa: Optional[TripleA] = TripleA()
    logging: Optional[LoggingComponents] = LoggingComponents() # Trying to avoid using "Logging" or "logging" as names for anything due to conflicts with standard lib.
    ntp: Optional[Ntp] = Ntp()
    ssh: Optional[Ssh] = Ssh()
    snmp: Optional[Snmp] = Snmp()

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
    stp: Optional[SpanningTree] = SpanningTree() 