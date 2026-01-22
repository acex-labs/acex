from pydantic import BaseModel, Field
from acex.models.attribute_value import AttributeValue
from enum import Enum
from typing import Optional, Dict, Literal


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
	
class SnmpInterfaceTrap(str, Enum):
    LINK_UP = "LINK_UP"
    LINK_DOWN = "LINK_DOWN"


class SnmpConfig(BaseModel):
	enabled: AttributeValue[bool] = False
	engine_id: Optional[AttributeValue[str]] = None
	source_interface: Optional[AttributeValue[str]] = None


class SnmpCommunity(BaseModel):
	name: AttributeValue[str]
	access: Optional[AttributeValue[SnmpAccess]] = SnmpAccess.READ_ONLY  # default read-only
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
	engine_id: Optional[AttributeValue[str]] = None  # security engine-id (optional)


class SnmpView(BaseModel):
	name: AttributeValue[str]
	oid: AttributeValue[str]
	included: Optional[AttributeValue[bool]] = True


class SnmpTrapServer(BaseModel):
	address: AttributeValue[str]
	port: Optional[AttributeValue[int]] = 162
	enabled: Optional[AttributeValue[bool]] = True
	version: Optional[AttributeValue[Literal["v2c", "v3"]]] = None
	community: Optional[AttributeValue[str]] = None  # used for v2c
	username: Optional[AttributeValue[str]] = None   # used for v3
	security_level: Optional[AttributeValue[SnmpSecurityLevel]] = None
	source_interface: Optional[AttributeValue[str]] = None


class SnmpTraps(BaseModel):
    authentication_failure: Optional[AttributeValue[bool]] = False
    link_down: Optional[AttributeValue[bool]] = False
    link_up: Optional[AttributeValue[bool]] = False
    cold_start: Optional[AttributeValue[bool]] = False
    warm_start: Optional[AttributeValue[bool]] = False

class Snmp(BaseModel):
	config: SnmpConfig = SnmpConfig()
	communities: Optional[Dict[str, SnmpCommunity]] = {}
	users: Optional[Dict[str, SnmpUser]] = {}
	trap_servers: Optional[Dict[str, SnmpTrapServer]] = {}
	trap: Optional[Dict[str, SnmpTraps]] = {}
	views: Optional[Dict[str, SnmpView]] = {}


