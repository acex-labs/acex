import asyncio
import re

from acex_devkit.drivers import State
from acex_devkit.models.lldp_neighbor import LldpNeighborEntry
from acex_devkit.models.platform import OS, Vendor
from acex_devkit.models.state import DeviceFacts

from acex_driver_cisco_ioscli.transport.transport import CiscoIOSTransport


class CiscoIOSState(State):
    async def get_facts(self, transport: CiscoIOSTransport) -> DeviceFacts:
        output = (await transport.execute(["show version"]))[0]
        return DeviceFacts(
            vendor=Vendor.cisco,
            os=OS.cisco_iosxe if re.search(r"Cisco IOS[ -]XE Software", output) else OS.cisco_ios,
            os_version=self.find(r"^Cisco IOS.*?Version ([^\s,]+)", output),
            hardware_model=self.find(r"Model Number\s+:\s*(\S+)", output)
            or self.find(r"^cisco (\S+) .*processor", output),
            serial_number=self.find(r"System Serial Number\s+:\s*(\S+)", output)
            or self.find(r"Processor board ID (\S+)", output),
        )

    async def get_lldp_neighbors(self, transport: CiscoIOSTransport) -> list[LldpNeighborEntry]:
        """LLDP neighbors, completed with CDP neighbors LLDP did not report."""
        try:
            lldp = (await asyncio.wait_for(transport.execute(["show lldp neighbors detail"]), timeout=10))[0]
        except Exception:
            # The connection state is unknown after a timeout, so CDP is not tried on this session.
            return []
        neighbors = self.parse_lldp(lldp) if self.enabled(lldp) else []
        try:
            cdp = (await asyncio.wait_for(transport.execute(["show cdp neighbors detail"]), timeout=10))[0]
        except Exception:
            return neighbors
        seen = {(n.local_interface, n.remote_device) for n in neighbors}
        if self.enabled(cdp):
            neighbors += [n for n in self.parse_cdp(cdp) if (n.local_interface, n.remote_device) not in seen]
        return neighbors

    @staticmethod
    def find(pattern: str, text: str) -> str | None:
        match = re.search(pattern, text, re.MULTILINE)
        return match.group(1) if match else None

    @staticmethod
    def enabled(output: str) -> bool:
        return "%" not in output[:40]

    def parse_lldp(self, raw: str) -> list[LldpNeighborEntry]:
        return [
            LldpNeighborEntry(
                local_interface=local,
                remote_device=device,
                remote_interface=self.find(r"Port id:\s*(\S+)", entry) or "",
                discovery_protocol="lldp",
            )
            for entry in re.split(r"-{20,}", raw)
            if (local := self.find(r"Local Intf:\s*(\S+)", entry))
            and (device := self.find(r"System Name:\s*(\S+)", entry))
        ]

    def parse_cdp(self, raw: str) -> list[LldpNeighborEntry]:
        return [
            LldpNeighborEntry(
                local_interface=local,
                remote_device=device.rstrip("."),
                remote_interface=self.find(r"Port ID.*?:\s*(\S+)", entry) or "",
                discovery_protocol="cdp",
            )
            for entry in re.split(r"-{20,}", raw)
            if (device := self.find(r"Device ID:\s*(\S+)", entry))
            and (local := self.find(r"Interface:\s*(\S+?),", entry))
        ]
