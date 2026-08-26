"""Vendor-agnostic model for PnP/bootstrap provisioning.

A BootstrapProfile describes everything a device needs in its initial
configuration so that it becomes reachable over SSH for full provisioning.
The actual CLI is rendered by the NED (driver) via ``render_bootstrap``.
"""

from typing import Literal

from pydantic import BaseModel, Field


class BootstrapUser(BaseModel):
    username: str
    password: str | None = None
    privilege: int = 15
    ssh_authorized_keys: list[str] = Field(default_factory=list)


class BootstrapProfile(BaseModel):
    """Everything needed to render an initial (bootstrap) configuration."""

    hostname: str
    ned_id: str | None = None
    management: dict = Field(default_factory=dict)
    """Free-form mgmt description interpreted by the driver template, e.g.
    {"interface": "Vlan123", "vlan_id": 123, "dhcp": true} or
    {"interface": "GigabitEthernet0/0", "address": "10.0.0.5/24", "gateway": "10.0.0.1"}"""
    users: list[BootstrapUser] = Field(default_factory=list)
    ssh: dict = Field(default_factory=lambda: {"enabled": True})
    domain_name: str | None = None
    name_servers: list[str] = Field(default_factory=list)
    ntp_servers: list[str] = Field(default_factory=list)
    source: Literal["pnp", "ztp", "manual"] = "pnp"
    extra: dict = Field(default_factory=dict)
    """Vendor-agnostic escape hatch passed through to the template."""
