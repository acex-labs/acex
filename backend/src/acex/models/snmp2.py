from pydantic import BaseModel, Field
from acex.models.attribute_value import AttributeValue
from enum import Enum
from typing import Optional, Dict, Literal, List


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
	source_interface: Optional[AttributeValue[str]] = None
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
	source_interface: Optional[AttributeValue[str]] = None

# ----------------------------
# Enum-based trap groups
# ----------------------------

class TrapSnmpAgentEvent(str, Enum):
	AUTHENTICATION = "authentication"
	LINKDOWN = "linkdown"
	LINKUP = "linkup"
	COLDSTART = "coldstart"
	WARMSTART = "warmstart"

class TrapFlowmonEvent(str, Enum):
	ENABLED = "enabled"

class TrapEntityPerfEvent(str, Enum):
	THROUGHPUT_NOTIF = "throughput-notif"

class TrapCallHomeEvent(str, Enum):
	MESSAGE_SEND_FAIL = "message-send-fail"
	SERVER_FAIL = "server-fail"

class TrapTtyEvent(str, Enum):
	ENABLED = "enabled"

class TrapEigrpEvent(str, Enum):
	ENABLED = "enabled"

class TrapOspfEvent(str, Enum):
	STATE_CHANGE = "state-change"
	ERRORS = "errors"
	RETRANSMIT = "retransmit"
	LSA = "lsa"

class TrapOspfCiscoSpecificStateEvent(str, Enum):
	NSSA_TRANS_CHANGE = "nssa-trans-change"
	SHAMLINK_INTERFACE = "shamlink-interface"
	SHAMLINK_NEIGHBOR = "shamlink-neighbor"

class TrapOspfCiscoSpecificEvent(str, Enum):
	ERRORS = "errors"
	RETRANSMIT = "retransmit"
	LSA = "lsa"
	STATE_CHANGE = "state-change"

class TrapBfdEvent(str, Enum):
	ENABLED = "enabled"

class TrapSmartLicenseEvent(str, Enum):
	ENABLED = "enabled"

class TrapAuthFrameworkEvent(str, Enum):
	SEC_VIOLATION = "sec-violation"

class TrapRepEvent(str, Enum):
	ENABLED = "enabled"

class TrapMemoryEvent(str, Enum):
	BUFFERPEAK = "bufferpeak"

class TrapConfigEvent(str, Enum):
	CONFIG_COPY = "config-copy"
	CONFIG = "config"
	CONFIG_CTID = "config-ctid"

class TrapEnergywiseEvent(str, Enum):
	ENABLED = "enabled"

class TrapFruCtrlEvent(str, Enum):
	ENABLED = "enabled"

class TrapEntityEvent(str, Enum):
	ENABLED = "enabled"

class TrapFlashEvent(str, Enum):
	INSERTION = "insertion"
	REMOVAL = "removal"
	LOWSPACE = "lowspace"

class TrapPowerEthernetEvent(str, Enum):
	POLICE = "police"
	GROUP_THRESHOLD = "group-threshold"

class TrapCpuEvent(str, Enum):
	THRESHOLD = "threshold"

class TrapSyslogEvent(str, Enum):
	ENABLED = "enabled"

class TrapUdldEvent(str, Enum):
	LINK_FAIL_RPT = "link-fail-rpt"
	STATUS_CHANGE = "status-change"

class TrapVtpEvent(str, Enum):
	ENABLED = "enabled"

class TrapVlanOpsEvent(str, Enum):
	VLANCREATE = "vlancreate"
	VLANDELETE = "vlandelete"

class TrapPortSecurityEvent(str, Enum):
	ENABLED = "enabled"

class TrapEnvMonEvent(str, Enum):
	ENABLED = "enabled"

class TrapStackwiseEvent(str, Enum):
	ENABLED = "enabled"

class TrapMvpnEvent(str, Enum):
	ENABLED = "enabled"

class TrapPwVcEvent(str, Enum):
	ENABLED = "enabled"

class TrapIpslaEvent(str, Enum):
	ENABLED = "enabled"

class TrapDhcpEvent(str, Enum):
	ENABLED = "enabled"

class TrapEventManagerEvent(str, Enum):
	ENABLED = "enabled"

class TrapIkeEvent(str, Enum):
	POLICY_ADD = "policy-add"
	POLICY_DELETE = "policy-delete"
	TUNNEL_START = "tunnel-start"
	TUNNEL_STOP = "tunnel-stop"

class TrapIpsecEvent(str, Enum):
	CRYPTOMAP_ADD = "cryptomap-add"
	CRYPTOMAP_DELETE = "cryptomap-delete"
	CRYPTOMAP_ATTACH = "cryptomap-attach"
	CRYPTOMAP_DETACH = "cryptomap-detach"
	TUNNEL_START = "tunnel-start"
	TUNNEL_STOP = "tunnel-stop"
	TOO_MANY_SAS = "too-many-sas"

class TrapOspfv3Event(str, Enum):
	STATE_CHANGE = "state-change"
	ERRORS = "errors"

class TrapIpMulticastEvent(str, Enum):
	ENABLED = "enabled"

class TrapMsdpEvent(str, Enum):
	ENABLED = "enabled"

class TrapPimEvent(str, Enum):
	NEIGHBOR_CHANGE = "neighbor-change"
	RP_MAPPING_CHANGE = "rp-mapping-change"
	INVALID_PIM_MESSAGE = "invalid-pim-message"

class TrapBridgeEvent(str, Enum):
	NEWROOT = "newroot"
	TOPOLOGYCHANGE = "topologychange"

class TrapStpxEvent(str, Enum):
	INCONSISTENCY = "inconsistency"
	ROOT_INCONSISTENCY = "root-inconsistency"
	LOOP_INCONSISTENCY = "loop-inconsistency"

class TrapBgpEvent(str, Enum):
	CBGP2 = "cbgp2"

class TrapHsrpEvent(str, Enum):
	ENABLED = "enabled"

class TrapIsisEvent(str, Enum):
	ENABLED = "enabled"

class TrapCefEvent(str, Enum):
	RESOURCE_FAILURE = "resource-failure"
	PEER_STATE_CHANGE = "peer-state-change"
	PEER_FIB_STATE_CHANGE = "peer-fib-state-change"
	INCONSISTENCY = "inconsistency"

class TrapLispEvent(str, Enum):
	ENABLED = "enabled"

class TrapNhrpEvent(str, Enum):
	NHS = "nhs"
	NHC = "nhc"
	NHP = "nhp"
	QUOTA_EXCEEDED = "quota-exceeded"

class TrapLocalAuthEvent(str, Enum):
	ENABLED = "enabled"

class TrapEntityDiagEvent(str, Enum):
	BOOT_UP_FAIL = "boot-up-fail"
	HM_TEST_RECOVER = "hm-test-recover"
	HM_THRESH_REACHED = "hm-thresh-reached"
	SCHEDULED_TEST_FAIL = "scheduled-test-fail"

class TrapMplsEvent(str, Enum):
	RFC_LDP = "rfc-ldp"
	LDP = "ldp"
	RFC_TRAFFIC_ENG = "rfc-traffic-eng"
	TRAFFIC_ENG = "traffic-eng"
	FAST_REROUTE_PROTECTED = "fast-reroute-protected"
	VPN = "vpn"
	RFC_VPN = "rfc-vpn"

class TrapBulkstatEvent(str, Enum):
	COLLECTION = "collection"
	TRANSFER = "transfer"

class TrapMacNotificationEvent(str, Enum):
	CHANGE = "change"
	MOVE = "move"
	THRESHOLD = "threshold"

class TrapErrdisableEvent(str, Enum):
	ENABLED = "enabled"

class TrapVlanMembershipEvent(str, Enum):
	ENABLED = "enabled"

class TrapTransceiverEvent(str, Enum):
	ALL = "all"

class TrapVrfmibEvent(str, Enum):
	VRF_UP = "vrf-up"
	VRF_DOWN = "vrf-down"
	VNET_TRUNK_UP = "vnet-trunk-up"
	VNET_TRUNK_DOWN = "vnet-trunk-down"

class TrapRfEvent(str, Enum):
	ENABLED = "enabled"

# En stor class med Enum	
class TrapEventOptions(str, Enum):
	VRF_UP = "vrf-up"
	VRF_DOWN = "vrf-down"
	VNET_TRUNK_UP = "vnet-trunk-up"
	VNET_TRUNK_DOWN = "vnet-trunk-down"
	ALL = "all"

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
