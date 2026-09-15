"""Cisco pluggable port modules.

Uplink network modules for the Catalyst 9000 series. A module declares only
its ports; the slot it occupies decides how those ports are numbered.

Port counts and speeds here come from Cisco product data, not from any
observed device - verify against the datasheet before relying on a module.
"""

from acex_devkit.device_types.cisco.base import CiscoNetworkModule
from acex_devkit.models.device_type import PortGroup, Speed

MGIG = [Speed.fast_ethernet, Speed.gigabit, Speed.two_and_half_gigabit, Speed.five_gigabit, Speed.ten_gigabit]


# --- Catalyst 9300 -----------------------------------------------------


class C9300_NM_4G(CiscoNetworkModule):
    models: list[str] = ["C9300-NM-4G"]
    ports: list[PortGroup] = [PortGroup(count=4, speeds=[Speed.gigabit])]


class C9300_NM_4M(CiscoNetworkModule):
    models: list[str] = ["C9300-NM-4M"]
    ports: list[PortGroup] = [PortGroup(count=4, speeds=MGIG)]


class C9300_NM_8X(CiscoNetworkModule):
    models: list[str] = ["C9300-NM-8X"]
    ports: list[PortGroup] = [PortGroup(count=8, speeds=[Speed.ten_gigabit])]


class C9300_NM_2Q(CiscoNetworkModule):
    models: list[str] = ["C9300-NM-2Q"]
    ports: list[PortGroup] = [PortGroup(count=2, speeds=[Speed.forty_gigabit])]


class C9300_NM_2Y(CiscoNetworkModule):
    models: list[str] = ["C9300-NM-2Y"]
    ports: list[PortGroup] = [PortGroup(count=2, speeds=[Speed.ten_gigabit, Speed.twentyfive_gigabit])]


# --- Catalyst 9300X ----------------------------------------------------


class C9300X_NM_8Y(CiscoNetworkModule):
    models: list[str] = ["C9300X-NM-8Y"]
    ports: list[PortGroup] = [PortGroup(count=8, speeds=[Speed.ten_gigabit, Speed.twentyfive_gigabit])]


class C9300X_NM_2C(CiscoNetworkModule):
    models: list[str] = ["C9300X-NM-2C"]
    ports: list[PortGroup] = [
        PortGroup(count=2, speeds=[Speed.forty_gigabit, Speed.hundred_gigabit]),
    ]


# --- Catalyst 9200 -----------------------------------------------------


class C9200_NM_4G(CiscoNetworkModule):
    models: list[str] = ["C9200-NM-4G"]
    ports: list[PortGroup] = [PortGroup(count=4, speeds=[Speed.gigabit])]


class C9200_NM_4X(CiscoNetworkModule):
    models: list[str] = ["C9200-NM-4X"]
    ports: list[PortGroup] = [PortGroup(count=4, speeds=[Speed.ten_gigabit])]


class C9200_NM_2Y(CiscoNetworkModule):
    models: list[str] = ["C9200-NM-2Y"]
    ports: list[PortGroup] = [PortGroup(count=2, speeds=[Speed.ten_gigabit, Speed.twentyfive_gigabit])]


class C9200_NM_2Q(CiscoNetworkModule):
    models: list[str] = ["C9200-NM-2Q"]
    ports: list[PortGroup] = [PortGroup(count=2, speeds=[Speed.forty_gigabit])]


C9300_NM_SLOT = [m for m in ("C9300-NM-4G", "C9300-NM-4M", "C9300-NM-8X", "C9300-NM-2Q", "C9300-NM-2Y")]
C9300X_NM_SLOT = ["C9300X-NM-8Y", "C9300X-NM-2C"]
C9200_NM_SLOT = ["C9200-NM-4G", "C9200-NM-4X", "C9200-NM-2Y", "C9200-NM-2Q"]
