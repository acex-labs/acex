from ipaddress import IPv4Interface, IPv6Interface

from acex.models import ExternalValue
from pydantic import validator
from sqlmodel import Field, SQLModel

"""
These models are not used, instead they are defined
in composed_configuration. But will eventually be moved
to their own file, like this one. 

"""


class Interface(SQLModel):
    enabled: bool | ExternalValue = Field(default=True)
    description: str | None | ExternalValue = None
    mac_address: str | None | ExternalValue = None
    ipv4: str | None | ExternalValue = None


class SubInterfaceAttributes(SQLModel):
    index: int | ExternalValue = 0
    enabled: bool | ExternalValue = Field(default=True)
    description: str | None | ExternalValue = None
    vlan_id: int | None | ExternalValue = None  # VLAN tagging för subinterface
    ipv4_address: str | None | ExternalValue = None
    ipv6_address: str | None | ExternalValue = None
    mtu: int | None | ExternalValue = None

    @validator("ipv4_address", pre=True, always=True)
    def validate_ipv4_address(cls, v):
        if v is None or isinstance(v, ExternalValue):
            return v
        if isinstance(v, str):
            try:
                return IPv4Interface(v)
            except Exception as exc:
                raise ValueError(f"Invalid IPv4 format: {v}") from exc
        return v

    @validator("ipv6_address", pre=True, always=True)
    def validate_ipv6_address(cls, v):
        if v is None or isinstance(v, ExternalValue):
            return v
        if isinstance(v, str):
            try:
                return IPv6Interface(v)
            except Exception as exc:
                raise ValueError(f"Invalid IPv6 format: {v}") from exc
        return v


class PhysicalInterface(Interface):
    type: str | ExternalValue = Field(default="ethernetCsmacd")
    index: int | ExternalValue = Field(default=0)
    speed: int | None | ExternalValue = None  # Speed in KBps
    switchport: bool | None | ExternalValue = None
    switchport_mode: str | None | ExternalValue = None  # e.g., 'access', 'trunk'
    switchport_untagged_vlan: int | None | ExternalValue = None
    switchport_trunk_vlans: list[int] | None | ExternalValue = None
    subinterfaces: list[SubInterfaceAttributes] | None | ExternalValue = None

    @validator("switchport_mode")
    def validate_switchport_mode(cls, v):
        if isinstance(v, ExternalValue):
            return v
        if v is not None and v not in ("access", "trunk"):
            raise ValueError("switchport_mode must be 'access' or 'trunk' if set")
        return v


class VirtualInterface(Interface):
    type: str | ExternalValue = Field(default="loopback")
    index: int | ExternalValue = Field(default=0)
