"""MikroTik switches: the CRS series, which run RouterOS as well as SwitchOS.

Port counts, speeds and cages come from MikroTik's product pages, not from an observed device. Only RouterOS is
declared: a CRS on SwitchOS is not a RouterOS device.
"""

from acex_devkit.device_types.mikrotik.base import MikroTikDevice
from acex_devkit.models.device_type import PortGroup, PortMedia, Speed


class CRS326_24G_2S_RM(MikroTikDevice):
    models: list[str] = ["CRS326-24G-2S+RM"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.gigabit], media=PortMedia.rj45),
        PortGroup(count=2, speeds=[Speed.gigabit, Speed.ten_gigabit], media=PortMedia.sfp_plus),
    ]
    notes: str | None = "The cages take both 1.25 Gbit/s SFP and 10G SFP+ modules."
