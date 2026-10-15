"""ZTP DHCP — `/ztp_dhcp/*`: the DHCP config rendered for ZTP."""

from __future__ import annotations

from acex_client.resources.base import ActionMixin, Resource, action


class ZtpDhcp(Resource, ActionMixin):
    """ZTP DHCP — `/ztp_dhcp`."""

    path = "/ztp_dhcp"

    @action("GET", "kea")
    def kea(self) -> dict:
        """The full Kea DHCPv4 config; bootstrap URLs use the address the client reached acex on."""
