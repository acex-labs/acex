from enum import StrEnum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field

from acex_devkit.models.acl_model import Acl
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.augment import Augmentable
from acex_devkit.models.augment import AugmentAttributes as AugmentAttributes
from acex_devkit.models.container_entry import ContainerEntry
from acex_devkit.models.logging import Console, FileLogging, LoggingConfig, LoggingEvents, RemoteServers, VtyLine
from acex_devkit.models.reference import Metadata as Metadata
from acex_devkit.models.reference import MetadataValueType as MetadataValueType
from acex_devkit.models.reference import Reference
from acex_devkit.models.reference import ReferenceFrom as ReferenceFrom
from acex_devkit.models.reference import ReferenceTo as ReferenceTo
from acex_devkit.models.reference import RenderedReference as RenderedReference
from acex_devkit.models.spanning_tree import SpanningTree

# --- Augments --------------------------------------------------------------
# Vendor/os-specific augments mount on target tree components via the
# `Augmentable` mixin. Devkit only knows about `AugmentAttributes` — the
# generic base — and uses `extra='allow'` to round-trip subclass-specific
# fields. Concrete augment payload classes (CiscoDeviceTrackingPolicy-
# Attributes, etc.) live in the backend alongside their ConfigComponent
# classes, so adding a new vendor augment requires no devkit edit.

# class AugmentAttributes(BaseModel):
#    """
#    Base for vendor/os-specific augments that mount on target tree components.
#
#    Subclasses live in the backend (next to their ConfigComponent) and add
#    typed payload fields. `extra='allow'` lets those fields round-trip
#    through serialize → JSON → re-validate without devkit knowing about them.
#
#    Augments live on a target node's `augments` dict, keyed by `type`. The
#    target itself is implicit (it's the node carrying this augment).
#    """
#    model_config = ConfigDict(extra="allow")
#    type: str
#
#
# class Augmentable(BaseModel):
#    """
#    Mixin that gives a target node a slot for vendor/os-specific augments.
#    Drivers walk `augments` per target and dispatch by augment type; targets
#    that no driver augments simply carry an empty dict.
#
#    `SerializeAsAny[AugmentAttributes]` makes Pydantic serialize each value
#    using its runtime type (the concrete subclass defined in backend),
#    not the declared base type. Combined with `extra='allow'` on
#    AugmentAttributes, this round-trips subclass-declared fields through
#    serialize → JSON → re-validate without devkit knowing the subclasses.
#    """
#    augments: Dict[str, SerializeAsAny[AugmentAttributes]] = {}


class SystemConfig(Augmentable):
    contact: AttributeValue[str] | None = None
    domain_name: AttributeValue[str] | None = None
    hostname: AttributeValue[str] | None = None
    location: AttributeValue[str] | None = None
    login_banner: AttributeValue[str] | None = None
    motd_banner: AttributeValue[str] | None = None


# class TripleA(BaseModel): ...
# Trying to avoid using "Logging" or "logging" as names for anything due to conflicts with standard lib.


class VtyLines(BaseModel):
    lines: dict[str, VtyLine] = {}


class LogFiles(BaseModel):
    files: dict[str, FileLogging] = {}


class LoggingComponents(BaseModel):
    config: LoggingConfig = LoggingConfig()
    console: Console | None = None
    remote_servers: RemoteServers | None = RemoteServers()
    events: LoggingEvents | None = None
    vty: VtyLines | None = VtyLines()
    files: LogFiles | None = LogFiles()


class NtpConfig(BaseModel):
    enabled: AttributeValue[bool] = AttributeValue(value=False)


class NtpServer(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("address",)
    address: AttributeValue[str]
    port: AttributeValue[int] | None = None
    version: AttributeValue[int] | None = None
    association_typ: AttributeValue[str] | None = None
    prefer: AttributeValue[bool] | None = None
    source_interface: AttributeValue[str] | None = None


class Ntp(BaseModel):
    config: NtpConfig | None = None
    servers: dict[str, NtpServer] | None = {}


class SshServer(Augmentable):
    enable: AttributeValue[bool] | None = None
    protocol_version: AttributeValue[int] | None = AttributeValue(value=2)
    timeout: AttributeValue[int] | None = None
    auth_retries: AttributeValue[int] | None = None
    source_interface: Reference | None = None


class AuthorizedKeyAlgorithms(StrEnum):
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


class AuthorizedKey(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("public_key",)
    algorithm: AttributeValue[AuthorizedKeyAlgorithms] | None = None
    public_key: AttributeValue[str] | None = None


class Ssh(BaseModel):
    config: SshServer | None = SshServer()
    host_keys: dict[str, AuthorizedKey] | None = {}


class LldpConfigAttributes(BaseModel):
    enabled: AttributeValue[bool] | None = None
    transmit_interval: AttributeValue[int] | None = None
    hold_time: AttributeValue[int] | None = None
    # The system name field shall contain an alpha-numeric string that indicates the system's
    # administratively assigned name.
    system_name: AttributeValue[str] | None = None
    # Comma-separated list of TLVs to suppress in advertisements. Values depend on device and vendor,
    # but common ones include "system_name", "system_description", "system_capabilities", "management_address", etc.
    suppress_tlv_advertisement: AttributeValue[list[str]] | None = None
    interfaces: dict[str, Reference] | None = {}


class CdpConfigAttributes(BaseModel):
    enabled: AttributeValue[bool] | None = None
    transmit_interval: AttributeValue[int] | None = None
    hold_time: AttributeValue[int] | None = None
    advertise_v2: AttributeValue[bool] | None = None  # Whether to advertise CDP version 2
    interfaces: dict[str, Reference] | None = {}


# class Lldp(BaseModel):
#    config: Optional[LldpConfigAttributes] = LldpConfigAttributes()
#    #interfaces: Optional[Dict[str, LldpInterfaceConfigAttributes]] = {}
#    interfaces: Optional[Dict[str, Reference]] = {}


class Vlan(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("vlan_id",)
    name: AttributeValue[str]
    vlan_id: AttributeValue[int] | None = None
    vlan_name: AttributeValue[str] | None = None
    network_instance: AttributeValue[str] | None = None


class StormControlAttributes(BaseModel):
    "Storm control thresholds for broadcast/multicast/unknown-unicast traffic on an interface."

    broadcast_pps: AttributeValue[int] | None = None
    multicast_pps: AttributeValue[int] | None = None
    unknown_unicast_pps: AttributeValue[int] | None = None
    action: AttributeValue[Literal["trap", "shutdown"]] | None = None


class InterfaceTemplateAttributes(ContainerEntry, Augmentable):
    "Reusable named set of interface attributes that interfaces can reference."

    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str]

    description: AttributeValue[str] | None = None
    enabled: AttributeValue[bool] | None = None

    # L1/L2
    switchport: AttributeValue[bool] | None = None
    switchport_mode: AttributeValue[Literal["access", "trunk"]] | None = None
    trunk_allowed_vlans: AttributeValue[list[int]] | None = None
    native_vlan: AttributeValue[int] | None = None
    access_vlan: AttributeValue[int] | None = None
    voice_vlan: AttributeValue[int] | None = None
    mtu: AttributeValue[int] | None = None
    speed: AttributeValue[int] | None = None
    duplex: AttributeValue[str] | None = None
    negotiation: AttributeValue[bool] | None = None
    dtp_negotiation: AttributeValue[bool] | None = None  # False renders as "switchport nonegotiate" on Cisco
    auto_mdix: AttributeValue[bool] | None = None

    # Operational signaling (default on; set False to suppress)
    logging_link_status: AttributeValue[bool] | None = None
    snmp_link_status_trap: AttributeValue[bool] | None = None

    # Storm control
    storm_control: StormControlAttributes | None = None

    # Spanning-tree
    stp_port_priority: AttributeValue[int] | None = None
    stp_cost: AttributeValue[int] | None = None
    stp_edge_port: AttributeValue[bool] | None = None  # 802.1w edge port; renders to "spanning-tree portfast" on Cisco
    stp_portfast: AttributeValue[bool] | None = None  # Cisco-explicit; renders to "spanning-tree portfast"
    stp_bpdu_filter: AttributeValue[bool] | None = None
    stp_bpdu_guard: AttributeValue[bool] | None = None
    stp_loop_guard: AttributeValue[bool] | None = None
    stp_root_guard: AttributeValue[bool] | None = None
    stp_link_type: AttributeValue[Literal["point-to-point", "shared"]] | None = None

    # LACP
    lacp_enabled: AttributeValue[bool] | None = None
    lacp_mode: AttributeValue[Literal["active", "passive", "on", "auto"]] | None = None
    lacp_port_priority: AttributeValue[int] | None = None
    lacp_interval: AttributeValue[Literal["fast", "slow"]] | None = None


class Interface(ContainerEntry, Augmentable):
    "Base class for all interfaces"

    identity_fields: ClassVar[tuple[str, ...]] = ("index", "type")
    index: AttributeValue[int]
    name: AttributeValue[str]

    description: AttributeValue[str] | None = None
    enabled: AttributeValue[bool] | None = None
    ipv4: AttributeValue[str] | None = None
    redirects: AttributeValue[bool] | None = None  # Regarding IP redirects.
    # Cisco true = yes / false = no, Juniper true = unrestricted / false = restricted
    proxy_arp: AttributeValue[bool] | None = None
    interface_template: Reference | None = None

    dtp_negotiation: AttributeValue[bool] | None = None  # False renders as "switchport nonegotiate" on Cisco
    logging_link_status: AttributeValue[bool] | None = None  # Default on; False suppresses link-state log events
    snmp_link_status_trap: AttributeValue[bool] | None = None  # Default on; False suppresses link-state SNMP traps
    storm_control: StormControlAttributes | None = None

    type: Literal[
        "ethernetCsmacd", "ieee8023adLag", "l3ipvlan", "softwareLoopback", "subinterface", "managementInterface"
    ] = "ethernetCsmacd"

    model_config = {"discriminator": "type"}


class EthernetCsmacdInterface(Interface):
    "Physical Interface"

    type: Literal["ethernetCsmacd"] = "ethernetCsmacd"

    # Egenskaper för fysiska interface
    stack_index: AttributeValue[int] | None = None
    module_index: AttributeValue[int] | None = None
    subinterfaces: list["SubInterface"] = Field(default_factory=list)
    speed: AttributeValue[int] | None = None
    duplex: AttributeValue[str] | None = None
    switchport: AttributeValue[bool] | None = None
    switchport_mode: AttributeValue[Literal["access", "trunk"]] | None = None
    trunk_allowed_vlans: AttributeValue[list[int]] | None = None
    native_vlan: AttributeValue[int] | None = None
    access_vlan: AttributeValue[int] | None = None
    vlan_id: AttributeValue[int] | None = None
    voice_vlan: AttributeValue[int] | None = None
    mtu: AttributeValue[int] | None = None  # No default set as it differs between devices and vendors
    negotiation: AttributeValue[bool] | None = None
    auto_mdix: AttributeValue[bool] | None = None
    # lldp_enabled: Optional[AttributeValue[bool]] = None
    # cdp_enabled: Optional[AttributeValue[bool]] = None

    # LACP relaterade attribut
    aggregate_id: AttributeValue[int] | None = None
    lacp_enabled: AttributeValue[bool] | None = None
    lacp_mode: AttributeValue[Literal["active", "passive", "on", "auto"]] | None = None
    lacp_port_priority: AttributeValue[int] | None = None
    # lacp_system_id_mac: Optional[AttributeValue[str]] = None
    lacp_interval: AttributeValue[Literal["fast", "slow"]] | None = None

    # Spanning-tree relaterade attribut
    stp_port_priority: AttributeValue[int] | None = None
    stp_cost: AttributeValue[int] | None = None
    stp_edge_port: AttributeValue[bool] | None = None
    stp_bpdu_filter: AttributeValue[bool] | None = None
    stp_bpdu_guard: AttributeValue[bool] | None = None
    stp_loop_guard: AttributeValue[bool] | None = None
    stp_root_guard: AttributeValue[bool] | None = None
    stp_portfast: AttributeValue[bool] | None = None
    stp_link_type: AttributeValue[Literal["point-to-point", "shared"]] | None = None


class Ieee8023adLagInterface(Interface):
    "LAG Interface"

    type: Literal["ieee8023adLag"] = "ieee8023adLag"
    aggregate_id: AttributeValue[int] | None = None
    members: AttributeValue[list[str]] | None = None
    max_ports: AttributeValue[int] | None = None
    switchport: AttributeValue[bool] | None = None
    switchport_mode: AttributeValue[Literal["access", "trunk"]] | None = None
    trunk_allowed_vlans: AttributeValue[list[int]] | None = None
    native_vlan: AttributeValue[int] | None = None
    mtu: AttributeValue[int] | None = None  # No default set as it differs between devices and vendors


class L3IpvlanInterface(Interface):
    "SVI Interface"

    type: Literal["l3ipvlan"] = "l3ipvlan"
    vlan_id: AttributeValue[int] | None = None


class SoftwareLoopbackInterface(Interface):
    "Loopback Interface"

    type: Literal["softwareLoopback"] = "softwareLoopback"

    # Loopback har varken vlan, duplex eller speed
    vlan_id: AttributeValue[int] | None = None
    ipv4: AttributeValue[str] | None = None


class SubInterface(Interface):
    "Subinterface"

    type: Literal["subinterface"] = "subinterface"

    vlan_id: AttributeValue[int] | None = None
    ipv4: AttributeValue[str] | None = None


class ManagementInterface(Interface):
    "Management Interface"

    type: Literal["managementInterface"] = "managementInterface"

    # Mgmt har inte vlan
    vlan_id: AttributeValue[int] | None = None


class StaticRouteNextHop(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("next_hop",)
    index: AttributeValue[int] | None = None
    next_hop: AttributeValue[str]  # can be an IP address or an interface. Reference will be handled in config component
    metric: AttributeValue[int] | None = None
    # Reference to parent static route, used for easier access in config component
    static_route: AttributeValue[str] | None = None
    network_instance: AttributeValue[str] | None = None


class StaticRoute(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("prefix",)
    route_name: AttributeValue[str] | None = None
    prefix: AttributeValue[str]
    next_hops: dict[str, StaticRouteNextHop] | None = {}
    network_instance: AttributeValue[str] | None = None


class Protocols(BaseModel):
    static_routes: dict[str, StaticRoute] | None = {}
    # OSPF, BGP, etc. can be added here as needed


class RouteTarget(BaseModel):
    value: AttributeValue[str] | None = None


class ImportExportPolicy(BaseModel):
    export_route_target: list[RouteTarget] | None = None
    import_route_target: list[RouteTarget] | None = None


class InterInstancePolicy(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ()
    import_export_policy: ImportExportPolicy


class NetworkInstance(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str]
    description: AttributeValue[str] | None = None
    vlans: dict[str, Vlan] | None = {}
    interfaces: dict[str, Reference] | None = {}
    inter_instance_policies: dict[str, InterInstancePolicy] | None = {}
    protocols: Protocols | None = Protocols()


class LacpConfig(BaseModel):
    system_priority: AttributeValue[int] | None = None
    system_id_mac: AttributeValue[str] | None = None
    load_balance_algorithm: (
        AttributeValue[
            list[
                Literal[
                    "src-mac",
                    "dst-mac",
                    "src-dst-mac",
                    "src-ip",
                    "dst-ip",
                    "src-dst-ip",
                    "src-port",
                    "dst-port",
                    "src-dst-port",
                ]
            ]
        ]
        | None
    ) = None


class Lacp(BaseModel):
    config: LacpConfig | None = LacpConfig()
    interfaces: dict[str, Interface] | None = {}


# SNMP
class SnmpAccess(StrEnum):
    READ_ONLY = "READ_ONLY"
    READ_WRITE = "READ_WRITE"


class SnmpSecurityLevel(StrEnum):
    NO_AUTH_NO_PRIV = "NO_AUTH_NO_PRIV"
    AUTH_NO_PRIV = "AUTH_NO_PRIV"
    AUTH_PRIV = "AUTH_PRIV"


class SnmpAuthProtocol(StrEnum):
    MD5 = "MD5"
    SHA1 = "SHA"
    SHA224 = "SHA-224"
    SHA256 = "SHA-256"
    SHA384 = "SHA-384"
    SHA512 = "SHA-512"


class SnmpPrivProtocol(StrEnum):
    DES = "DES"
    TRIPLE_DES = "3DES"
    AES128 = "AES128"
    AES192 = "AES192"
    AES256 = "AES256"


class SnmpConfig(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str]
    enabled: AttributeValue[bool] = AttributeValue(value=False)
    engine_id: AttributeValue[str] | None = None
    location: AttributeValue[str] | None = None
    contact: AttributeValue[str] | None = None


class SnmpCommunity(ContainerEntry, Augmentable):
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str]
    community: AttributeValue[str] | None = None  # Community string
    # access: Optional[AttributeValue[SnmpAccess]] = AttributeValue(value=SnmpAccess.READ_ONLY)
    # view: Optional[Reference] = None
    ipv4acl: Reference | None = None  # Cisco and similar vendors
    ipv6acl: Reference | None = None
    # source_interface: Optional[Reference] = None


class SnmpGroup(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str]
    access: AttributeValue[SnmpAccess] | None = AttributeValue(value=SnmpAccess.READ_ONLY)
    ipv4acl: Reference | None = None  # Cisco and similar vendors
    ipv6acl: Reference | None = None
    # source_interface: Optional[Reference] = None
    users: dict[str, Reference] | None = {}  # Users that belong to this group. Only relevant for SNMPv3.
    views: dict[str, Reference] | None = {}  # Views that this group has access to.


class SnmpUser(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("username",)
    username: AttributeValue[str]
    security_level: AttributeValue[SnmpSecurityLevel] | None = AttributeValue(value=SnmpSecurityLevel.NO_AUTH_NO_PRIV)
    auth_protocol: AttributeValue[SnmpAuthProtocol] | None = None
    auth_password: AttributeValue[str] | None = None
    priv_protocol: AttributeValue[SnmpPrivProtocol] | None = None
    priv_password: AttributeValue[str] | None = None


class SnmpView(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str]
    oid: AttributeValue[str]
    included: AttributeValue[bool] | None = AttributeValue(value=True)
    view: AttributeValue[str] | None = None


class SnmpViewAttributes(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str]
    oids: dict[str, SnmpView] | None = {}


class SnmpServer(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("address",)
    name: AttributeValue[str] | None = None
    address: AttributeValue[str] | None = None
    port: AttributeValue[int] | None = AttributeValue(value=162)
    enabled: AttributeValue[bool] | None = AttributeValue(value=True)
    version: AttributeValue[Literal["v2c", "v3"]] | None = None
    community: AttributeValue[str] | None = None
    username: AttributeValue[str] | None = None
    security_level: AttributeValue[SnmpSecurityLevel] | None = None
    source_interface: Reference | None = None
    network_instance: AttributeValue[str] | None = None
    group: Reference | None = None  # Only relevant for SNMPv3.


# ----------------------------
# Enum-based trap groups
# ----------------------------
# En stor class med Enum
class TrapEventOptions(StrEnum):
    VRF_UP = "vrf-up"
    VRF_DOWN = "vrf-down"
    VNET_TRUNK_UP = "vnet-trunk-up"
    VNET_TRUNK_DOWN = "vnet-trunk-down"
    ALL = "all"
    RfEvent = "enabled"
    VlanMembershipEvent = "enabled"
    ErrdisableEvent = "enabled"
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


class TrapEvent(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("event_name",)
    name: AttributeValue[str] | None = None
    event_name: AttributeValue[TrapEventOptions] | None = None


# class SnmpTrap(BaseModel): ...


class Snmp(BaseModel):
    config: dict[str, SnmpConfig] | None = {}
    communities: dict[str, SnmpCommunity] | None = {}
    groups: dict[str, SnmpGroup] | None = {}
    users: dict[str, SnmpUser] | None = {}
    trap_servers: dict[str, SnmpServer] | None = {}
    trap_events: dict[str, TrapEvent] | None = {}
    views: dict[str, SnmpViewAttributes] | None = {}


# AAA
class aaaBaseClass(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ()  # key is identity (e.g. "default", "console")
    name: AttributeValue[str] | None = None


class aaaTacacsAttributes(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("address",)
    port: AttributeValue[int] | None = None
    secret_key: AttributeValue[str] | None = None
    secret_key_hashed: AttributeValue[str] | None = None
    address: AttributeValue[str] | None = None
    timeout: AttributeValue[int] | None = None
    source_interface: Reference | None = None
    server_group: AttributeValue[str] | None = None


class aaaRadiusAttributes(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("address",)
    auth_port: AttributeValue[int] | None = None
    acct_port: AttributeValue[int] | None = None
    secret_key: AttributeValue[str] | None = None
    secret_key_hashed: AttributeValue[str] | None = None
    address: AttributeValue[str] | None = None
    timeout: AttributeValue[int] | None = None
    source_interface: Reference | None = None
    retransmit_attempts: AttributeValue[int] | None = None
    server_group: AttributeValue[str] | None = None


class aaaServerGroupAttributes(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ()  # key is the group name
    """
    Define a AAA server group that can contain multiple TACACS+ and/or RADIUS servers.

    Type is used to tell future renderers what kind of server group this is.
    Example:
    type = 'tacacs' or type = 'radius'

    The tacacs and radius attributes expect a reference to the aaaTacacs and aaaRadius models respectively.

    Example in config map:
    enable = True
    type = 'tacacs'
    tacacs = [tacacs_server1, tacacs_server2]
    radius = radius_server1

    Cisco example:
    aaa group server tacacs+ TACACS-GROUP
     server name tacacs_server1
     server name tacacs_server2
    """
    enable: AttributeValue[bool] | None = None
    type: AttributeValue[Literal["tacacs", "radius"]] | None = None
    tacacs: dict[str, aaaTacacsAttributes] | None = {}
    radius: dict[str, aaaRadiusAttributes] | None = {}


# Authentication Models
class aaaAuthenticationMethods(aaaBaseClass):
    """
    Define the authentiation methods used by AAA. If you define a server group using the "aaaServerGroup" model,
    you can reference it here by its name, but only as a string.

    Example in config map:
    method = ['TACACS_GROUP','LOCAL']

    Cisco example:
    aaa authentication login default group TACACS-GROUP-NEW local
    """

    # method: Optional[List[str]] = None
    # Ex. ['TACACS_GROUP','LOCAL', 'default', 'enable'] - TACACS_GROUP is reference to server group
    method: AttributeValue[str] | None = None
    # Method could handle a reference to a server group in the future. For now we only use strings.
    # Important for users to know this.

    # Cisco example:
    # aaa authentication login default group TACACS-GROUP-NEW local
    # aaa authentication enable default group TACACS-GROUP-NEW enable


class authenticationUser(aaaBaseClass):
    identity_fields: ClassVar[tuple[str, ...]] = ("username",)
    username: AttributeValue[str] | None = None
    password: AttributeValue[str] | None = None
    password_hahsed: AttributeValue[str] | None = None
    ssh_key: AttributeValue[str] | None = None
    role: AttributeValue[str] | None = None


class aaaAuthenticationUsers(aaaBaseClass):
    username: dict[str, authenticationUser] | None = {}


class adminUser(aaaBaseClass):
    admin_password: AttributeValue[str] | None = None
    admin_password_hashed: AttributeValue[str] | None = None


class aaaAuthenticationAdminUsers(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ()
    config: dict[str, adminUser] | None = {}


class aaaAuthenticationConfig(ContainerEntry, Augmentable):
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str] | None = None  # ex. default, CONSOLE, etc.
    methods: dict[str, aaaAuthenticationMethods] | None = {}


class aaaAuthentication(BaseModel):
    # config: Optional[Dict[str, aaaAuthenticationMethods]] = {}
    config: aaaAuthenticationConfig = aaaAuthenticationConfig()
    admin_user: dict[str, aaaAuthenticationAdminUsers] | None = {}
    users: dict[str, aaaAuthenticationUsers] | None = {}


# Authorization Models
class aaaAuthorizationMethods(aaaBaseClass):
    """
    Define the authorization methods used by AAA. If you define a server group using the "aaaServerGroup" model,
    you can reference it here by its name, but only as a string.

    Example in config map:
    method = ['TACACS_GROUP','LOCAL']

    Cisco example:
    aaa authorization login default group TACACS-GROUP-NEW local
    """

    # method: Optional[List[str]] = None # Ex. ['TACACS_GROUP','LOCAL']
    method: AttributeValue[str] | None = None


class aaaAuthorizationEvents(aaaBaseClass):
    """
    Define authorization events.

    Cisco example:
    aaa authorization config-commands
    aaa authorization console
    """

    # events: Optional[List[str]] = Field(default_factory=list) # Ex. ['config-commands','console']
    # event: Optional[AttributeValue[List[str]]] = None
    event: AttributeValue[str] | None = None


class aaaAuthorizationConfig(ContainerEntry, Augmentable):
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str] | None = None  # ex. default, CONSOLE, etc.
    methods: dict[str, aaaAuthorizationMethods] | None = {}
    events: dict[str, aaaAuthorizationEvents] | None = {}


class aaaAuthorization(BaseModel):
    # config: Optional[Dict[str, aaaAuthorizationMethods]] = {}
    config: aaaAuthorizationConfig = aaaAuthorizationConfig()
    # methods: Optional[Dict[str, aaaAuthorizationMethods]] = {}
    # events: Optional[Dict[str, aaaAuthorizationEvents]] = {}


# Accounting Models
class aaaAccountingMethods(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ()
    """
    Define the accounting methods used by AAA. If you define a server group using the "aaaServerGroup" model,
    you can reference it here by its name, but only as a string.

    Example in config map:
    method = ['TACACS_GROUP','LOCAL']

    Cisco example:
    aaa accounting login default group TACACS-GROUP-NEW local
    """
    # method: Optional[List[str]] = None # Ex. ['TACACS_GROUP','LOCAL']
    method: AttributeValue[str] | None = None


class aaaAccountingEvents(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ()
    """
    Define accounting events.

    Cisco example:
    aaa accounting send stop-record authentication failure
    """
    # events: Optional[List[str]] = Field(default_factory=list) # Ex. ['send','stop-record','authentication', 'failure']
    event: AttributeValue[str] | None = None


class aaaAccountingConfig(ContainerEntry, Augmentable):
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str] | None = None  # ex. default, CONSOLE, etc.
    methods: dict[str, aaaAccountingMethods] | None = {}
    events: dict[str, aaaAccountingEvents] | None = {}


class aaaAccounting(BaseModel):
    # config: Optional[Dict[str, aaaAccountingMethods]] = {}
    config: aaaAccountingConfig = aaaAccountingConfig()
    # methods: Optional[Dict[str, aaaAccountingMethods]] = {}
    # events: Optional[Dict[str, aaaAccountingEvents]] = {}


class aaaGlobalAttributes(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str] | None = None  # ex. default, CONSOLE, etc.
    enabled: AttributeValue[bool] | None = False  # default False


class TripleA(BaseModel):
    config: aaaGlobalAttributes = aaaGlobalAttributes()
    server_groups: dict[str, aaaServerGroupAttributes] | None = {}
    authentication: aaaAuthentication = aaaAuthentication()
    authorization: aaaAuthorization = aaaAuthorization()
    accounting: aaaAccounting = aaaAccounting()


class VTPAttributes(Augmentable):
    domain_name: AttributeValue[str] | None = None
    mode: AttributeValue[Literal["server", "client", "transparent", "off"]] | None = None
    version: AttributeValue[Literal[1, 2, 3]] | None = None
    password: AttributeValue[str] | None = None
    password_hashed: AttributeValue[str] | None = None


class VTP(BaseModel):
    config: VTPAttributes = VTPAttributes()


class DHCPSnoopingAttributes(Augmentable):
    enabled: AttributeValue[bool] | None = None
    # VLANs where DHCP snooping is enabled, key is VLAN ID, value is reference to VLAN
    vlans: dict[str, Reference] | None = {}
    # Interfaces that are trusted for DHCP snooping, key is interface name, value is reference to interface
    trust_interfaces: dict[str, Reference] | None = {}
    option82: AttributeValue[bool] | None = None  # Whether DHCP snooping option 82 is enabled


class DhcpRelayServerAttributes(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("address",)
    address: AttributeValue[str] | None = None
    network_instance: AttributeValue[str] | None = None
    interfaces: dict[str, Reference] | None = {}


class DhcpRelay(BaseModel):
    relay_servers: dict[str, DhcpRelayServerAttributes] | None = {}


class Dhcp(BaseModel):
    snooping: DHCPSnoopingAttributes | None = DHCPSnoopingAttributes()
    relay: DhcpRelay | None = DhcpRelay()


class ServicesAttributes(Augmentable):
    name: AttributeValue[str] | None = None
    http: AttributeValue[bool] | None = None  # for webgui access
    https: AttributeValue[bool] | None = None  # for webgui access


class Services(BaseModel):
    config: ServicesAttributes | None = ServicesAttributes()
    # name: Optional[AttributeValue[str]] = None
    # http: Optional[AttributeValue[bool]] = None # for webgui access
    # https: Optional[AttributeValue[bool]] = None # for webgui access


class NetflowFormat(StrEnum):
    IPFIX = "IPFIX"
    NETFLOW_V9 = "NetFlow v9"
    NETFLOW_V5 = "NetFlow v5"


class NetflowRecordIpv4Match(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str]
    # Leaf-level ipv4 matches (Cisco style "match ipv4 <field>"). True = match this field, False = No.
    # None = Ignore the field
    # Reference to parent record, used for easier access in config component
    netflow_record: AttributeValue[str] | None = None
    dscp: AttributeValue[bool] | None = None
    fragmentation: AttributeValue[bool] | None = None
    header_length: AttributeValue[bool] | None = None
    id: AttributeValue[bool] | None = None
    length: AttributeValue[bool] | None = None
    option: AttributeValue[bool] | None = None
    precedence: AttributeValue[bool] | None = None
    protocol: AttributeValue[bool] | None = None
    section: AttributeValue[str] | None = None
    tos: AttributeValue[bool] | None = None
    total_length: AttributeValue[bool] | None = None
    ttl: AttributeValue[bool] | None = None
    version: AttributeValue[bool] | None = None


class NetflowRecordAttributes(ContainerEntry, BaseModel):  # Cisco flow record
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str]
    match_ipv4: NetflowRecordIpv4Match | None = None
    # match_ipv4: Optional[Dict[str, NetflowRecordIpv4Match]] = {}
    application_name: AttributeValue[bool] | None = None

    # Escape hatch for vendor-specific match knobs not yet modeled
    # keeping a flexible option if needed. Not advertised to users.
    match_vendor_specific: AttributeValue[dict[str, Any]] | None = None

    collect_timestamp_absolute_first: AttributeValue[bool] | None = None
    collect_timestamp_absolute_last: AttributeValue[bool] | None = None


class NetflowCollectorAttributes(ContainerEntry, BaseModel):  # Cisco flow monitor
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str]
    records: dict[str, Reference] | None = {}  # References to records, used for easier access in config component
    exporters: dict[str, Reference] | None = {}  # References to exporters, used for easier access in config component
    cache_inactive: AttributeValue[int] | None = None
    cache_active: AttributeValue[int] | None = None
    interfaces: dict[str, Reference] | None = {}  # allow for disabling netflow on specific interfaces


class NetflowExporterOptions(ContainerEntry, BaseModel):
    # Mostly timeouts atm
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str]
    interface_table_timeout: AttributeValue[int] | None = None
    vrf_table_timeout: AttributeValue[int] | None = None
    sampler_table: AttributeValue[bool] | None = None
    application_table_timeout: AttributeValue[int] | None = None
    application_attributes_timeout: AttributeValue[int] | None = None
    # Reference to parent exporter, used for easier access in config component
    netflow_exporter: AttributeValue[str] | None = None


class NetflowExporterAttributes(ContainerEntry, BaseModel):  # Cisco flow exporter
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str]
    address: AttributeValue[str] | None = None
    port: AttributeValue[int] | None = None
    netflow_format: AttributeValue[str] | None = None
    source_interface: Reference | None = None
    network_instance: AttributeValue[str] | None = None
    options: NetflowExporterOptions | None = None


class NetflowGlobalConfigAttributes(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str]
    enabled: AttributeValue[bool] | None = None
    version: AttributeValue[int] | None = None


class Netflow(BaseModel):
    config: NetflowGlobalConfigAttributes | None = None
    records: dict[str, NetflowRecordAttributes] | None = {}
    exporters: dict[str, NetflowExporterAttributes] | None = {}
    collectors: dict[str, NetflowCollectorAttributes] | None = {}


class SflowMonitoringAttributes(BaseModel): ...


class SflowForwardingAttributes(BaseModel): ...  # collector?


class SflowCollectorAttributes(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("address",)
    address: AttributeValue[str] | None = None  # Destination IP address of the sFlow collector
    port: AttributeValue[int] | None = None  # UDP
    source_address: AttributeValue[str] | None = None
    network_instance: AttributeValue[str] | None = None  # VRF
    interfaces: dict[str, Reference] | None = {}  # allow for disabling sflow on specific interfaces


class SfloGlobalConfigAttributes(BaseModel):
    enabled: AttributeValue[bool] | None = None
    # version: Optional[AttributeValue[int]] = None
    dscp: AttributeValue[int] | None = None  # range: 0..63
    # Sets the maximum number of bytes to be copied from a sampled packet (content within one
    # specific sample of a packet).
    sample_size: AttributeValue[int] | None = None
    polling_interval: AttributeValue[int] | None = None  # seconds
    # sampling rate is 1/N packets. An implementation may implement the sampling rate as a
    # statistical average, rather than a strict periodic sampling.
    ingress_sampling_rate: AttributeValue[int] | None = None
    # sampling rate is 1/N packets. An implementation may implement the sampling rate as a
    # statistical average, rather than a strict periodic sampling.
    egress_sampling_rate: AttributeValue[int] | None = None


class Sflow(BaseModel):
    # enabled: Optional[AttributeValue[bool]] = None
    # version: Optional[AttributeValue[int]] = None
    # dscp: Optional[AttributeValue[int]] = None # range: 0..63
    # sample_size: Optional[AttributeValue[int]] = None
    # polling_interval: Optional[AttributeValue[int]] = None
    # ingress_sampling_rate: Optional[AttributeValue[int]] = None
    # egress_sampling_rate: Optional[AttributeValue[int]] = None
    collector: dict[str, SflowCollectorAttributes] | None = {}
    # Similar structure to Netflow can be implemented here for sFlow-specific attributes


class Sampling(BaseModel):
    netflow: Netflow | None = Netflow()
    # sflow: Optional[Sflow] = Sflow() # Sflow can be added in the future, similar structure to Netflow


class DnsServerAttributes(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("address",)
    address: AttributeValue[str] | None = None
    # Keeping option to allow for use where needed, even if default DNS port is 53
    port: AttributeValue[int] | None = None
    source_interface: Reference | None = None  # Keeping option to allow for use where needed
    network_instance: AttributeValue[str] | None = None


class Dns(BaseModel):
    # Placeholder for DNS configuration. Can be expanded with actual DNS attributes as needed.
    # enabled: Optional[AttributeValue[bool]] = None
    dns_servers: dict[str, DnsServerAttributes] | None = {}  # key is server name, value is IP address


class ClockConfig(BaseModel):
    timezone: AttributeValue[str] | None = None


class Clock(BaseModel):
    config: ClockConfig | None = None


class System(BaseModel):
    config: SystemConfig = SystemConfig()
    clock: Clock | None = Clock()
    aaa: TripleA | None = TripleA()
    # Trying to avoid using "Logging" or "logging" as names for anything due to conflicts with standard lib.
    logging: LoggingComponents | None = LoggingComponents()
    ntp: Ntp | None = Ntp()
    ssh: Ssh | None = Ssh()
    snmp: Snmp | None = Snmp()
    vtp: VTP | None = VTP()
    dhcp: Dhcp | None = Dhcp()
    dns: Dns | None = Dns()
    services: Services | None = Services()


# For different types of interfaces that are fine for response model:
InterfaceType = (
    EthernetCsmacdInterface
    | Ieee8023adLagInterface
    | L3IpvlanInterface
    | SoftwareLoopbackInterface
    | SubInterface
    | ManagementInterface
)


class ComposedConfiguration(BaseModel):
    system: System | None = System()
    acl: Acl | None = Acl()
    lldp: LldpConfigAttributes | None = LldpConfigAttributes()
    cdp: CdpConfigAttributes | None = CdpConfigAttributes()
    lacp: Lacp | None = Lacp()
    interfaces: dict[str, InterfaceType] = {}
    interface_templates: dict[str, InterfaceTemplateAttributes] = {}
    network_instances: dict[str, NetworkInstance] = {"global": NetworkInstance(name="global")}
    stp: SpanningTree | None = SpanningTree()
    sampling: Sampling | None = Sampling()


"""
GUIDELINES FOR COMPOSED CONFIGURATION:

1. All values must always be typed as AttributeValue.
2. Containers must always be defined as hierarchical pydantic types, no dicts as placeholders.
3. Component collections must use a typed container class (e.g. RemoteServers, VtyLines) with an inner
   Dict[str, BaseModel] field — the key identifies the component. Raw Dict fields are not allowed at
   the container level.
4. Default values for Optional containers are always an empty instance of the container class, e.g.
   Optional[RemoteServers] = RemoteServers(). Never default to None or a raw empty dict for collections.
"""
