import re

from acex_devkit.drivers import Actions
from acex_devkit.exceptions import DriverException
from acex_devkit.models.actions import (
    ArpTableParams,
    ArpTableResult,
    InterfaceStatusParams,
    InterfaceStatusResult,
    IpRouteParams,
    IpRouteResult,
    LookupArpParams,
    LookupArpResult,
    LookupMacAddressParams,
    LookupMacAddressResult,
    MacAddressTableParams,
    MacAddressTableResult,
    PingParams,
    PingResult,
    TracerouteParams,
    TracerouteResult,
)

from acex_driver_cisco_ioscli.transport.transport import CiscoIOSTransport

from .arp import Arp
from .interfaces import Interfaces
from .ip_route import IpRoute
from .mac_address_table import MacAddressTable
from .ping import Ping
from .traceroute import Traceroute


class CiscoIOSActions(Actions):
    """Sends each action's commands and builds its result from what the command classes read."""

    #: Seconds a show command may take; a large table is slow to print.
    SHOW_TIMEOUT = 60
    #: A line saying why a command wasn't run, but not a legend's "% - next hop override".
    ERROR = re.compile(r"^\s*(?P<error>%(?! -).*?)\s*$", re.MULTILINE)

    async def ping(self, transport: CiscoIOSTransport, params: PingParams) -> PingResult:
        return Ping.parse(await transport.send(Ping.command(params), timeout=Ping.timeout(params)), params)

    async def get_mac_address_table(
        self, transport: CiscoIOSTransport, params: MacAddressTableParams
    ) -> MacAddressTableResult:
        output = await self.show(transport, MacAddressTable.command(vlan=params.vlan, interface=params.interface))
        return MacAddressTableResult(entries=MacAddressTable.parse(output, vlan=params.vlan))

    async def lookup_mac_address(
        self, transport: CiscoIOSTransport, params: LookupMacAddressParams
    ) -> LookupMacAddressResult:
        entries = []
        for vlan in params.vlans or [None]:
            output = await self.show(transport, MacAddressTable.command(mac=params.mac, vlan=vlan))
            entries += MacAddressTable.parse(output, vlan=vlan)
        return LookupMacAddressResult(mac=params.mac, entries=entries)

    async def get_ip_route(self, transport: CiscoIOSTransport, params: IpRouteParams) -> IpRouteResult:
        output = await self.show(transport, IpRoute.command(params), nothing=IpRoute.NOT_IN_TABLE)
        return IpRouteResult(vrf=params.vrf, routes=IpRoute.parse(output))

    async def get_arp_table(self, transport: CiscoIOSTransport, params: ArpTableParams) -> ArpTableResult:
        output = await self.show(transport, Arp.command(vrf=params.vrf, filter=params.interface))
        return ArpTableResult(vrf=params.vrf, entries=Arp.parse(output))

    async def lookup_arp(self, transport: CiscoIOSTransport, params: LookupArpParams) -> LookupArpResult:
        output = await self.show(transport, Arp.command(vrf=params.vrf, filter=str(params.ip)))
        return LookupArpResult(ip=params.ip, vrf=params.vrf, entry=Arp.find(output, params.ip))

    async def traceroute(self, transport: CiscoIOSTransport, params: TracerouteParams) -> TracerouteResult:
        output = await self.show(transport, Traceroute.command(params), timeout=Traceroute.timeout(params))
        return Traceroute.parse(output)

    async def get_interface_status(
        self, transport: CiscoIOSTransport, params: InterfaceStatusParams
    ) -> InterfaceStatusResult:
        output = await self.show(transport, Interfaces.command(params.interface))
        return InterfaceStatusResult(interfaces=Interfaces.parse(output))

    @classmethod
    async def show(
        cls, transport: CiscoIOSTransport, command: str, timeout: int | None = None, nothing: tuple[str, ...] = ()
    ) -> str:
        """IOS reports a command it couldn't run on a line of its own: "% Invalid input detected", "% VRF X
        does not exist". Such a line fails the action, unless it holds one of `nothing`: a way of saying
        there is nothing to show, e.g. "% Network not in table"."""
        output = await transport.send(command, timeout=timeout or cls.SHOW_TIMEOUT)
        match = cls.ERROR.search(output)
        if match is None:
            return output
        if any(text in match["error"] for text in nothing):
            return ""
        raise DriverException(f"{command}: {match['error']}")
