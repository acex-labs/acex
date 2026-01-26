from pydantic import BaseModel, Field
from acex.models.attribute_value import AttributeValue
from enum import Enum
from typing import Optional, Dict, Literal, List

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
	source_interface: Optional[Reference] = None
	location: Optional[AttributeValue[str]] = None
	contact: Optional[AttributeValue[str]] = None


class SnmpCommunity(BaseModel):
	name: AttributeValue[str]
	access: Optional[AttributeValue[SnmpAccess]] = SnmpAccess.READ_ONLY
	view: Optional[AttributeValue[str]] = None
	ipv4_acl: Optional[AttributeValue[str]] = None
	ipv6_acl: Optional[AttributeValue[str]] = None


class SnmpUser(BaseModel):
	username: AttributeValue[str]
	security_level: Optional[AttributeValue[SnmpSecurityLevel]] = SnmpSecurityLevel.NO_AUTH_NO_PRIV
	auth_protocol: Optional[AttributeValue[SnmpAuthProtocol]] = None
	auth_password: Optional[AttributeValue[str]] = None
	priv_protocol: Optional[AttributeValue[SnmpPrivProtocol]] = None
	priv_password: Optional[AttributeValue[str]] = None
	engine_id: Optional[AttributeValue[str]] = None


class SnmpView(BaseModel):
	name: AttributeValue[str]
	oid: AttributeValue[str]
	included: Optional[AttributeValue[bool]] = True


class SnmpServer(BaseModel):
	address: AttributeValue[str]
	port: Optional[AttributeValue[int]] = 162
	enabled: Optional[AttributeValue[bool]] = True
	version: Optional[AttributeValue[Literal["v2c", "v3"]]] = None
	community: Optional[AttributeValue[str]] = None
	username: Optional[AttributeValue[str]] = None
	security_level: Optional[AttributeValue[SnmpSecurityLevel]] = None
	source_interface: Optional[AttributeValue[str | Reference]] = None
	network_instance: Optional[AttributeValue[str | Reference]] = None

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
	event_name: TrapEventOptions

#class SnmpTrap(BaseModel): ...

class Snmp(BaseModel):
	config: SnmpConfig = SnmpConfig()
	communities: Optional[Dict[str, SnmpCommunity]] = {}
	users: Optional[Dict[str, SnmpUser]] = {}
	trap_servers: Optional[Dict[str, SnmpServer]] = {}
	trap_events: Optional[list[TrapEvent]] = None
	views: Optional[Dict[str, SnmpView]] = {}
