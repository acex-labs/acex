from pydantic import BaseModel
from ipaddress import IPv4Network, IPv6Network
from acex.models.attribute_value import AttributeValue
from enum import Enum
from typing import Optional, Dict, Literal

class AclProtoclOptions(str, Enum):
    TCP = 'tcp'
    UDP = 'udp'
    ICMP = 'icmp'
    OSPF = 'ospf'
    IP = 'ip'
    ANY = 'any'

class IpAclOptions(BaseModel):
    description: Optional[AttributeValue[str]] = None
    source_port: Optional[AttributeValue[str]] = None # e.g., "100-200"
    destination_port: Optional[AttributeValue[str]] = None # e.g., "300-400"
    protocol: Optional[AttributeValue[AclProtoclOptions]] = None # e.g., TCP(6), UDP(17), ICMP(1) # The protocol carried in the IP packet, expressed either as its IP protocol number, or by a defined identity.
    sequence_id: Optional[AttributeValue[int]] = None
    log: Optional[AttributeValue[bool]] = None # Enable logging for matching packets.
    dscp: Optional[AttributeValue[int]] = None # Value of diffserv codepoint.

class Ipv4AclEntryAttributes(IpAclOptions):
    '''
    Docstring for AclIpv4

    * description: Description of the ACL entry. Renark in Cisco language.
    * sequence_id: Sequence number of the ACL entry.
    * log: Enable logging for matching packets.
    * source_port: Source port or port range.
    * destination_port: Destination port or port range.
    * source_address: Source IPv4 address or prefix.
    * destination_address: Destination IPv4 address or prefix.
    * dscp: Value of diffserv codepoint.
    * ipv4acl: Reference to the ACL this entry belongs to.
    
    * protocol: tcp, udp, icmp, ospf, ip, any # The protocol carried in the IP packet, expressed either as its IP protocol number, or by a defined identity.
    '''
    source_address: Optional[AttributeValue[IPv4Network | Literal['any']]] = None # Source IPv4 address prefix.
    destination_address: Optional[AttributeValue[IPv4Network | Literal['any']]] = None # Destination IPv4 address prefix.
    ipv4_acl: Optional[AttributeValue[str]] = None # Reference to the ACL Set this entry belongs to.

class Ipv6AclEntryAttributes(IpAclOptions):
    '''
    Docstring for AclIpv4

    * description: Description of the ACL entry. Renark in Cisco language.
    * sequence_id: Sequence number of the ACL entry.
    * log: Enable logging for matching packets.
    * source_port: Source port or port range.
    * destination_port: Destination port or port range.
    * source: Source IPv6 address or prefix.
    * destination: Destination IPv6 address or prefix.
    * dscp: Value of diffserv codepoint.
    * ipv6acl: Reference to the ACL this entry belongs to.
    
    * protocol: tcp, udp, icmp, ospf, ip, any # The protocol carried in the IP packet, expressed either as its IP protocol number, or by a defined identity.
    '''
    source_address: Optional[AttributeValue[IPv6Network | Literal['any']]] = None # Source IPv6 address prefix.
    destination_address: Optional[AttributeValue[IPv6Network | Literal['any']]] = None # Destination IPv6 address prefix.
    ipv6_acl: Optional[AttributeValue[str]] = None # Reference to the ACL Set this entry belongs to.

class Ipv4AclAttributes(BaseModel):
    name: AttributeValue[str]
    type: AttributeValue[str] = "ipv4_acl"
    acl_entries: Optional[Dict[str, Ipv4AclEntryAttributes]] = {}

class Ipv6AclAttributes(BaseModel):
    name: AttributeValue[str]
    type: AttributeValue[str] = "ipv6_acl"
    acl_entries: Optional[Dict[str, Ipv6AclEntryAttributes]] = {}
    
class Acl(BaseModel):
    ipv4_acls: Optional[Dict[str, Ipv4AclAttributes]] = {}
    ipv6_acls: Optional[Dict[str, Ipv6AclAttributes]] = {}

