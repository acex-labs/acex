from typing import Optional, Dict, List, Union, Any, get_origin, get_args
from sqlmodel import SQLModel, Field
from ipaddress import IPv4Interface, IPv6Interface, IPv4Address
from pydantic import validator, field_serializer, root_validator
from pydantic import BaseModel

from acex.models import ExternalValue



"""
These models are not used, instead they are defined
in composed_configuration. But will eventually be moved
to their own file, like this one. 

"""

class Interface(SQLModel): 
    enabled: Union[bool, ExternalValue] = Field(default=True)
    description: Union[Optional[str], ExternalValue] = None
    mac_address: Union[Optional[str], ExternalValue] = None
    ipv4: Union[Optional[str], ExternalValue] = None


class SubInterfaceAttributes(SQLModel):
    index: Union[int, ExternalValue] = 0
    enabled: Union[bool, ExternalValue] = Field(default=True)
    description: Union[Optional[str], ExternalValue] = None
    vlan_id: Union[Optional[int], ExternalValue] = None  # VLAN tagging för subinterface
    ipv4_address: Union[Optional[str], ExternalValue] = None
    ipv6_address: Union[Optional[str], ExternalValue] = None
    mtu: Union[Optional[int], ExternalValue] = None
    
    @validator("ipv4_address", pre=True, always=True)
    def validate_ipv4_address(cls, v):
        if v is None or isinstance(v, ExternalValue):
            return v
        if isinstance(v, str):
            try:
                return IPv4Interface(v)
            except Exception:
                raise ValueError(f"Invalid IPv4 format: {v}")
        return v
        
    @validator("ipv6_address", pre=True, always=True)
    def validate_ipv6_address(cls, v):
        if v is None or isinstance(v, ExternalValue):
            return v
        if isinstance(v, str):
            try:
                return IPv6Interface(v)
            except Exception:
                raise ValueError(f"Invalid IPv6 format: {v}")
        return v
    

class PhysicalInterface(Interface):
    type: Union[str, ExternalValue] = Field(default="ethernetCsmacd")
    index: Union[int, ExternalValue] = Field(default=0)
    speed: Union[Optional[int], ExternalValue] = None  # Speed in KBps
    switchport: Union[Optional[bool], ExternalValue] = None
    switchport_mode: Union[Optional[str], ExternalValue] = None  # e.g., 'access', 'trunk'
    switchport_untagged_vlan: Union[Optional[int], ExternalValue] = None
    switchport_trunk_vlans: Union[Optional[List[int]], ExternalValue] = None
    subinterfaces: Union[Optional[List[SubInterfaceAttributes]], ExternalValue] = None

    @validator("switchport_mode")
    def validate_switchport_mode(cls, v):
        if isinstance(v, ExternalValue):
            return v
        if v is not None and v not in ("access", "trunk"):
            raise ValueError("switchport_mode must be 'access' or 'trunk' if set")
        return v


class VirtualInterface(Interface):
    type: Union[str, ExternalValue] = Field(default="loopback")
    index: Union[int, ExternalValue] = Field(default=0)

