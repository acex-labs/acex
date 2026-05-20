"""Cisco IOS / IOS-XE DHCP snooping augments."""

from typing import Literal

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.dhcp import DHCPSnooping
from acex_devkit.models.composed_configuration import AugmentAttributes


class CiscoDhcpSnoopingTrackServerAttributes(AugmentAttributes):
    type: Literal["cisco_dhcp_snooping_track_server"] = "cisco_dhcp_snooping_track_server"
    all_dhcp_acks: bool = False


class CiscoDhcpSnoopingTrackServer(Augment):
    """Renders to ``ip dhcp snooping track server [all-dhcp-acks]``."""
    type = "cisco_dhcp_snooping_track_server"
    model_cls = CiscoDhcpSnoopingTrackServerAttributes
    valid_targets = (DHCPSnooping,)
    default_vendor = "cisco"
