"""ZTP DHCP scopes — `/ztp_dhcp_scopes/*`: the IPv4 networks the ZTP DHCP server hands out addresses in."""

from __future__ import annotations

from acex_devkit.models.ztp import ZtpDhcpScopeCreate, ZtpDhcpScopeResponse, ZtpDhcpScopeUpdate

from acex_client.resources.base import ActionMixin, Resource, action


class ZtpDhcpScopes(Resource, ActionMixin):
    """ZTP DHCP scopes — `/ztp_dhcp_scopes`. IPv4 only; scopes may not overlap."""

    path = "/ztp_dhcp_scopes"

    @action("GET", "")
    def query(self) -> list[ZtpDhcpScopeResponse]: ...

    @action("POST", "")
    def create(self, payload: ZtpDhcpScopeCreate) -> ZtpDhcpScopeResponse:
        """A scope that doesn't hold together or overlaps another raises AcexValidationError."""

    @action("PATCH", "{id}")
    def update(self, id: int, payload: ZtpDhcpScopeUpdate) -> ZtpDhcpScopeResponse:
        """Change the fields sent; the scope as a whole is checked again."""

    @action("DELETE", "{id}")
    def delete(self, id: int) -> None: ...
