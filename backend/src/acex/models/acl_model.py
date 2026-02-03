from pydantic import BaseModel, IPvAnyNetwork
#from ipaddress import IPv4Network, IPv6Network
from acex.models.attribute_value import AttributeValue
from enum import Enum
from typing import Optional, Dict, Literal

#class AclTransportAttributes(BaseModel):
#    source_port: Optional[AttributeValue[str]] = None # e.g., "100-200"
#    source_port_set: Optional[AttributeValue[str]] = None # Reference to port-set
#    destination_port: Optional[AttributeValue[str]] = None # e.g., "300-
#    destination_port_set: Optional[AttributeValue[str]] = None # Reference to port-set
#    detail: Optional[AttributeValue[str]] = False # ??????
#
#class AclIpv6Attributes(BaseModel): ...
#
#class AclIcmpv4Attributes(BaseModel): 
#    type: Optional[AttributeValue[int]] = None # Optional ICMPv4 type
#    code: Optional[AttributeValue[int]] = None # Optional ICMPv4 code
#
#class AclIpv4Attributes(BaseModel):
#    '''
#    Docstring for AclIpv4
#
#    * source_address: Optional[AttributeValue[str]] = None # Source IPv4 address prefix.
#    * source_address_prefix_set: Optional[AttributeValue[str]] = None # Reference to a IPv4 address prefix Set to match the source address. path reference: /defined-sets/ipv4-prefix-sets/ipv4-prefix-set/name
#    * destination_address: Optional[AttributeValue[str]] = None # Destination IPv4 address prefix.
#    * destination_address_prefix_set: Optional[AttributeValue[str]] = None # Reference to a IPv4 address prefix set to match
#    the destination address. path reference: /defined-sets/ipv4-prefix-sets/ipv4-prefix-set/name
#    * dscp: Optional[AttributeValue[int]] = None # Value of diffserv codepoint.
#    * dscp_set: Optional[AttributeValue[str]] = None
#        * A list of DSCP values to be matched for incoming packets. AN OR match should be performed, 
#        * such that a packet must match one of the values defined in this list. 
#        * If the field is left empty then any DSCP value matches unless the 'dscp' leaf is specified. 
#        * It is not valid to specify both 'dscp' and 'dscp-set together.'
#    
#    * length: Optional[AttributeValue[str]] = None # e.g., "100-200"
#        * In the IPv4 header field, this field is known as the Total Length. Total Length is the length
#        * of the datagram, measured in octets, including internet header and data. In the IPv6 header 
#        * field, this field is known as the Payload Length, which is the length of the IPv6 payload, 
#        * i.e., the rest of the packet following the IPv6 header, in octets.
#    
#    * protocol: Optional[AttributeValue[int]] = None # e.g., TCP(6), UDP(17), ICMP(1) # The protocol carried in the IP packet, expressed either as its IP protocol number, or by a defined identity.
#    * hop_limit: Optional[AttributeValue[int]] = None # TTL
#    * icmpv4: path to the icmpv4 object. Use AclIcmpv4 model in configmap when defining this object.
#    '''
#    source_address: Optional[AttributeValue[str]] = None # Source IPv4 address prefix.
#    source_address_prefix_set: Optional[AttributeValue[str]] = None # Reference to a IPv4 address prefix Set to match the source address. path reference: /defined-sets/ipv4-prefix-sets/ipv4-prefix-set/name
#    destination_address: Optional[AttributeValue[str]] = None # Destination IPv4 address prefix.
#    destination_address_prefix_set: Optional[AttributeValue[str]] = None # Reference to a IPv4 address prefix set to match the destination address. path reference: /defined-sets/ipv4-prefix-sets/ipv4-prefix-set/name
#    dscp: Optional[AttributeValue[int]] = None # Value of diffserv codepoint.
#    
#    dscp_set: Optional[AttributeValue[str]] = None
#    # A list of DSCP values to be matched for incoming packets. AN OR match should be performed, 
#    # such that a packet must match one of the values defined in this list. 
#    # If the field is left empty then any DSCP value matches unless the 'dscp' leaf is specified. 
#    # It is not valid to specify both 'dscp' and 'dscp-set together.'
#
#    length: Optional[AttributeValue[str]] = None # e.g., "100-200"
#    # In the IPv4 header field, this field is known as the Total Length. Total Length is the length
#    # of the datagram, measured in octets, including internet header and data. In the IPv6 header 
#    # field, this field is known as the Payload Length, which is the length of the IPv6 payload, 
#    # i.e., the rest of the packet following the IPv6 header, in octets.
#
#    protocol: Optional[AttributeValue[int]] = None # e.g., TCP(6), UDP(17), ICMP(1) # The protocol carried in the IP packet, expressed either as its IP protocol number, or by a defined identity.
#    hop_limit: Optional[AttributeValue[int]] = None # TTL
#    icmpv4: Optional[Dict[str, AclIcmpv4Attributes]] = {}
#
#class AclEntryAttributes(BaseModel): 
#    sequence_id: AttributeValue[int] = None  # Unique identifier for the ACL entry
#    description: Optional[AttributeValue[str]] = None
#    l2: str = "l2"  # Layer 2 ACL
#    ipv4: Optional[Dict[str, AclIpv4Attributes]] = {}
#    mpls: str = "mpls"  # MPLS ACL
#    ipv6: str = "ipv6"  # IPv6 ACL
#    transport: Optional[Dict[str, AclTransportAttributes]] = {}

class transportOptions(BaseModel):
    source_port: Optional[AttributeValue[str]] = None # e.g., "100-200"
    #source_port_set: Optional[AttributeValue[str]] = None # Reference to port-set
    destination_port: Optional[AttributeValue[str]] = None # e.g., "300-
    #destination_port_set: Optional[AttributeValue[str]] = None # Reference to port-set
    protocol: Optional[AttributeValue[str]] = None # e.g., TCP(6), UDP(17), ICMP(1) # The protocol carried in the IP packet, expressed either as its IP protocol number, or by a defined identity.

class Ipv4Acl(transportOptions):
    '''
    Docstring for AclIpv4

    * source_address: Source IPv4 address prefix.
    * destination_address: Destination IPv4 address prefix.
    * dscp: Value of diffserv codepoint.
    
    * protocol: e.g., TCP(6), UDP(17), ICMP(1) # The protocol carried in the IP packet, expressed either as its IP protocol number, or by a defined identity.
    '''
    description: Optional[AttributeValue[str]] = None
    sequence_id: Optional[AttributeValue[int]] = None
    source: Optional[AttributeValue[IPvAnyNetwork | Literal['any']]] = None # Source IPv4 address prefix.
    destination: Optional[AttributeValue[IPvAnyNetwork | Literal['any']]] = None # Destination IPv4 address prefix.
    log: Optional[AttributeValue[bool]] = None # Enable logging for matching packets.
    dscp: Optional[AttributeValue[int]] = None # Value of diffserv codepoint.

class Ipv6Acl(transportOptions):
    description: Optional[AttributeValue[str]] = None
    sequence_id: Optional[AttributeValue[int]] = None
    source: Optional[AttributeValue[IPvAnyNetwork | Literal['any']]] = None # Source IPv6 address prefix.
    destination: Optional[AttributeValue[IPvAnyNetwork | Literal['any']]] = None # Destination IPv6 address prefix.
    log: Optional[AttributeValue[bool]] = None # Enable logging for matching packets.
    dscp: Optional[AttributeValue[int]] = None # Value of diffserv codepoint.

class AclEntries(BaseModel):
    ipv4acl : Optional[Dict[str, Ipv4Acl]] = {}
    ipv6acl : Optional[Dict[str, Ipv6Acl]] = {}

class AclSetsAttributes(BaseModel):
    acl_entries: Optional[Dict[str, AclEntries]] = {} 
    
class AclSets(BaseModel):
    acl_set: AclSetsAttributes = AclSetsAttributes()

class Acl(BaseModel):
    #acl_sets: AclSets = AclSets()
    acl_entries: AclEntries = AclEntries()