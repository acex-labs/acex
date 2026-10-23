import asyncio
import re

from acex_devkit.configdiffer import Diff
from acex_devkit.drivers import Codec, NetworkElementDriver, State, Transport
from acex_devkit.exceptions import AuthenticationFailed, ConnectionTimeout, DriverException
from acex_devkit.models.codec_result import ParseResult, RenderResult
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.lldp_neighbor import LldpNeighborEntry
from acex_devkit.models.management_connection import ConnectionType
from acex_devkit.models.ned import Platform
from acex_devkit.models.node_response import NodeInstance
from acex_devkit.models.platform import OS, Vendor
from acex_devkit.models.state import DeviceFacts
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

from .normalizer import JunosNormalizer
from .renderer import JunosCLIRenderer


class JunosCLITransport(Transport[str]):
    """SSH to Junos via netmiko, which is synchronous, so every call runs in a thread.

    Payloads are `set` / `delete` lines, one per line, committed as one change.
    """

    connection_types = {ConnectionType.ssh}

    PORT = 22

    async def open(self) -> None:
        login = self.credential("userpass")
        device = {
            "device_type": "juniper_junos",
            "host": self.address,
            "username": login.fields["username"],
            "password": login.fields["password"],
            "port": self.PORT,
            "conn_timeout": 30,
        }
        try:
            self.conn = await asyncio.to_thread(ConnectHandler, **device)
        except NetmikoAuthenticationException as e:
            raise AuthenticationFailed(f"Authentication to {self.address} failed") from e
        except NetmikoTimeoutException as e:
            raise ConnectionTimeout(f"Connection to {self.address} timed out") from e

    async def close(self) -> None:
        try:
            await asyncio.to_thread(self.conn.disconnect)
        except Exception:
            pass

    async def get_config(self) -> str:
        # `display set` flattens the hierarchy into reproducible `set` lines; `no-more` disables paging.
        command = "show configuration | display set | no-more"
        return await asyncio.to_thread(self.conn.send_command, command, read_timeout=120)

    async def apply(self, payload: str) -> str:
        commands = [line.strip() for line in payload.splitlines() if line.strip()]
        if not commands:
            return ""
        return await asyncio.to_thread(self.commit, commands)

    async def execute(self, request: list[str]) -> list[str]:
        return await asyncio.to_thread(self.send_commands, request)

    def commit(self, commands: list[str]) -> str:
        """Load the commands and commit them. Without the commit, leaving configure mode discards them."""
        output = self.conn.send_config_set(commands, exit_config_mode=False)
        return output + self.conn.commit(and_quit=True)

    def send_commands(self, commands: list[str]) -> list[str]:
        return [self.conn.send_command(command, read_timeout=120) for command in commands]


class JunosCodec(Codec[str]):
    """Junos `set` syntax. Configuration and patches render to `set` / `delete` lines."""

    normalizer = JunosNormalizer()

    def render(self, config: ComposedConfiguration, node: NodeInstance) -> RenderResult[str]:
        return RenderResult(payload=JunosCLIRenderer().render(config, node.asset))

    def parse(self, raw: str, node: NodeInstance) -> ParseResult:
        raise DriverException("Parsing Junos configuration is not implemented yet")

    def render_patch(self, diff: Diff, node: NodeInstance) -> str:
        return JunosCLIRenderer().render_patch(diff, node)

    def normalize(self, raw: str) -> str:
        return self.normalizer.normalize(raw).config

    def mask(self, raw: str) -> str:
        return self.normalizer.mask(raw).config


class JunosState(State):
    async def get_facts(self, transport: JunosCLITransport) -> DeviceFacts:
        version, hardware = await transport.execute(["show version", "show chassis hardware"])
        chassis = re.search(r"^Chassis\s+(\S+)\s+(\S+)", hardware, re.MULTILINE)
        return DeviceFacts(
            vendor=Vendor.juniper,
            os=OS.juniper_junos,
            os_version=self.find(r"^Junos:\s*(\S+)", version),
            hardware_model=self.find(r"^Model:\s*(\S+)", version) or (chassis.group(2) if chassis else None),
            serial_number=chassis.group(1) if chassis else None,
        )

    async def get_lldp_neighbors(self, transport: JunosCLITransport) -> list[LldpNeighborEntry]:
        try:
            raw = (await transport.execute(["show lldp neighbors"]))[0]
        except Exception:
            return []
        return self.parse_lldp_table(raw)

    @staticmethod
    def find(pattern: str, text: str) -> str | None:
        match = re.search(pattern, text, re.MULTILINE)
        return match.group(1) if match else None

    @staticmethod
    def parse_lldp_table(raw: str) -> list[LldpNeighborEntry]:
        """Parse the fixed-width table:

        Local Interface  Parent Interface  Chassis Id         Port info  System Name
        ge-0/0/0         -                 00:11:22:33:44:55  ge-0/0/1   peer-switch
        """
        return [
            LldpNeighborEntry(
                local_interface=parts[0],
                remote_device=parts[-1],
                remote_interface=parts[-2],
                discovery_protocol="lldp",
            )
            for line in raw.splitlines()
            if line.strip() and not line.lower().startswith("local interface")
            if len(parts := line.split()) >= 5
        ]


class JunosCLI(NetworkElementDriver):
    """Juniper Junos CLI driver."""

    codec_class = JunosCodec
    transport_class = JunosCLITransport
    state_class = JunosState

    platforms = [Platform(vendor=Vendor.juniper, os=OS.juniper_junos)]
