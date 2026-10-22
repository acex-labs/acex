"""Operational state a driver can read from a device."""

from enum import StrEnum

from pydantic import BaseModel

from acex_devkit.models.platform import OS, Vendor


class StateKind(StrEnum):
    """One kind of operational state. Each value maps to `State.get_<value>`."""

    FACTS = "facts"
    LLDP_NEIGHBORS = "lldp_neighbors"
    ARP_TABLE = "arp_table"


class DeviceFacts(BaseModel):
    """What a device says it is. Read during discovery, before any node instance exists."""

    vendor: Vendor
    os: OS
    os_version: str | None = None
    hardware_model: str | None = None
    serial_number: str | None = None


class ArpEntry(BaseModel):
    ip_address: str
    mac_address: str
    interface: str
