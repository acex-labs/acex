from pydantic import BaseModel
from ipaddress import IPv4Network, IPv6Network
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.container_entry import ContainerEntry
from enum import Enum
from typing import ClassVar, Optional, Dict, Literal

class AclProtoclOptions(str, Enum):
    TCP = 'tcp'
    UDP = 'udp'
    ICMP = 'icmp'
    OSPF = 'ospf'
    IP = 'ip'
    ANY = 'any'

class IpAclOptions(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("sequence_id",)
    description: Optional[AttributeValue[str]] = None
    source_port: Optional[AttributeValue[str]] = None # e.g., "100-200"
    destination_port: Optional[AttributeValue[str]] = None # e.g., "300-400"
    protocol: Optional[AttributeValue[AclProtoclOptions]] = None # e.g., TCP(6), UDP(17), ICMP(1) # The protocol carried in the IP packet, expressed either as its IP protocol number, or by a defined identity.
    sequence_id: Optional[AttributeValue[int]] = None
    log: Optional[AttributeValue[bool]] = None # Enable logging for matching packets.
    dscp: Optional[AttributeValue[int]] = None # Value of diffserv codepoint.
    action: Optional[AttributeValue[str]] = None # e.g., "permit" or "deny" in Cisco or ACCEPT, DROP in Juniper

class Ipv4AclEntryAttributes(IpAclOptions):
    '''
    Docstring for AclIpv4

    * description: Description of the ACL entry. Remark in Cisco language.
    * sequence_id: Sequence number of the ACL entry.
    * log: Enable logging for matching packets.
    * source_port: Source port or port range.
    * destination_port: Destination port or port range.
    * source_address: Source IPv4 address or prefix.
    * destination_address: Destination IPv4 address or prefix.
    * dscp: Value of diffserv codepoint.
    * action: Action to be taken for matching packets. e.g., "permit" or "deny" in Cisco or ACCEPT, DROP in Juniper
    * ipv4acl: Reference to the ACL this entry belongs to.
    
    * protocol: tcp, udp, icmp, ospf, ip, any # The protocol carried in the IP packet, expressed either as its IP protocol number, or by a defined identity.
    '''
    source_address: Optional[AttributeValue[IPv4Network | Literal['any']]] = None # Source IPv4 address prefix.
    destination_address: Optional[AttributeValue[IPv4Network | Literal['any']]] = None # Destination IPv4 address prefix.
    ipv4_acl: Optional[AttributeValue[str]] = None # Reference to the ACL Set this entry belongs to.

class Ipv6AclEntryAttributes(IpAclOptions):
    '''
    Docstring for AclIpv6

    * description: Description of the ACL entry. Remark in Cisco language.
    * sequence_id: Sequence number of the ACL entry.
    * log: Enable logging for matching packets.
    * source_port: Source port or port range.
    * destination_port: Destination port or port range.
    * source: Source IPv6 address or prefix.
    * destination: Destination IPv6 address or prefix.
    * dscp: Value of diffserv codepoint.
    * action: Action to be taken for matching packets. e.g., "permit" or "deny" in Cisco or ACCEPT, DROP in Juniper
    * ipv6acl: Reference to the ACL this entry belongs to.
    
    * protocol: tcp, udp, icmp, ospf, ip, any # The protocol carried in the IP packet, expressed either as its IP protocol number, or by a defined identity.
    '''
    source_address: Optional[AttributeValue[IPv6Network | Literal['any']]] = None # Source IPv6 address prefix.
    destination_address: Optional[AttributeValue[IPv6Network | Literal['any']]] = None # Destination IPv6 address prefix.
    ipv6_acl: Optional[AttributeValue[str]] = None # Reference to the ACL Set this entry belongs to.

class Ipv4AclAttributes(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str]
    type: AttributeValue[str] = "ipv4_acl"
    acl_entries: Optional[Dict[str, Ipv4AclEntryAttributes]] = None

class Ipv6AclAttributes(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str]
    type: AttributeValue[str] = "ipv6_acl"
    acl_entries: Optional[Dict[str, Ipv6AclEntryAttributes]] = None
    
class Acl(BaseModel):
    ipv4_acls: Optional[Dict[str, Ipv4AclAttributes]] = None
    ipv6_acls: Optional[Dict[str, Ipv6AclAttributes]] = None
