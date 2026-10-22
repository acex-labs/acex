import asyncio
import re

from acex_devkit.configdiffer import Diff
from acex_devkit.drivers import Codec, NetworkElementDriver, State, Transport
from acex_devkit.exceptions import AuthenticationFailed, ConnectionTimeout
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.lldp_neighbor import LldpNeighborEntry
from acex_devkit.models.management_connection import ConnectionType
from acex_devkit.models.ned import Platform
from acex_devkit.models.node_response import NodeInstance
from acex_devkit.models.platform import OS, Vendor
from acex_devkit.models.state import DeviceFacts
from scrapli.driver.core import AsyncIOSXEDriver
from scrapli.exceptions import ScrapliAuthenticationFailed, ScrapliTimeout

from .normalizer import CiscoIOSNormalizer
from .parser import CiscoIOSCLIParser
from .renderer import CiscoIOSCLIRenderer


class CiscoIOSTransport(Transport[str]):
    """SSH to Cisco IOS / IOS-XE via scrapli. Payloads are CLI text, one command per line."""

    connection_types = {ConnectionType.ssh}

    PORT = 22

    # Legacy KEX/ciphers for older IOS devices that don't support modern algorithms
    LEGACY_ASYNCSSH_OPTIONS = {
        "kex_algs": [
            "diffie-hellman-group-exchange-sha256",
            "diffie-hellman-group-exchange-sha1",
            "diffie-hellman-group14-sha256",
            "diffie-hellman-group14-sha1",
            "diffie-hellman-group1-sha1",
        ],
    }

    async def open(self) -> None:
        login = self.credential("userpass")
        enable = self.credential("privilege_escalation", required=False)
        self.conn = AsyncIOSXEDriver(
            host=self.address,
            auth_username=login.fields["username"],
            auth_password=login.fields["password"],
            auth_secondary=enable.fields["password"] if enable else login.fields["password"],
            auth_strict_key=False,
            port=self.PORT,
            timeout_socket=30,
            timeout_ops=120,
            transport="asyncssh",
            transport_options={"asyncssh": self.LEGACY_ASYNCSSH_OPTIONS},
        )
        try:
            await self.conn.open()
        except ScrapliAuthenticationFailed as e:
            if isinstance(e.__cause__, asyncio.TimeoutError):
                raise ConnectionTimeout(f"Connection to {self.address} timed out") from e
            raise AuthenticationFailed(f"Authentication to {self.address} failed") from e
        except ScrapliTimeout as e:
            raise ConnectionTimeout(f"Connection to {self.address} timed out") from e

    async def close(self) -> None:
        try:
            await self.conn.close()
        except Exception:
            pass

    async def get_config(self) -> str:
        return (await self.conn.send_command("show running-config", timeout_ops=120)).result

    async def apply(self, payload: str) -> str:
        commands = [line.strip() for line in payload.splitlines() if line.strip() and line.strip() != "!"]
        if not commands:
            return ""
        return (await self.conn.send_configs(commands)).result

    async def execute(self, request: list[str]) -> list[str]:
        return [r.result for r in await self.conn.send_commands(request, timeout_ops=120)]


class CiscoIOSCodec(Codec[str]):
    """Cisco IOS CLI syntax. Configuration and patches render to CLI text."""

    normalizer = CiscoIOSNormalizer()

    def render(self, config: ComposedConfiguration, node: NodeInstance) -> str:
        return CiscoIOSCLIRenderer().render(config, node.asset)

    def parse(self, raw: str, node: NodeInstance) -> ComposedConfiguration:
        # The parser keeps state while parsing, so each call gets its own.
        return ComposedConfiguration.model_validate(CiscoIOSCLIParser().parse(raw))

    def render_patch(self, diff: Diff, node: NodeInstance) -> str:
        return CiscoIOSCLIRenderer().render_patch(diff, node)

    def normalize(self, raw: str) -> str:
        return self.normalizer.normalize(raw).config

    def mask(self, raw: str) -> str:
        return self.normalizer.mask(raw).config


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


class CiscoIOSCLIDriver(NetworkElementDriver):
    """Cisco IOS CLI driver."""

    codec_class = CiscoIOSCodec
    transport_class = CiscoIOSTransport
    state_class = CiscoIOSState

    platforms = [Platform(vendor=Vendor.cisco, os=OS.cisco_iosxe)]
