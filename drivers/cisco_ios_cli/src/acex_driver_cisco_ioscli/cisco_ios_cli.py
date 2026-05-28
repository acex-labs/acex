
from contextlib import asynccontextmanager
from typing import Optional
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.node_response import NodeListItem
from acex_devkit.models.management_connection import ManagementConnection
from scrapli.driver.core import AsyncIOSXEDriver
from scrapli.exceptions import ScrapliTimeout

from acex_devkit.drivers import NetworkElementDriver, TransportBase
from acex_devkit.configdiffer import Diff

from .renderer import CiscoIOSCLIRenderer
from .parser import CiscoIOSCLIParser
from .normalizer import CiscoIOSNormalizer

# Legacy KEX/ciphers for older IOS devices that don't support modern algorithms
_LEGACY_ASYNCSSH_OPTIONS = {
    "kex_algs": [
        "diffie-hellman-group-exchange-sha256",
        "diffie-hellman-group-exchange-sha1",
        "diffie-hellman-group14-sha256",
        "diffie-hellman-group14-sha1",
        "diffie-hellman-group1-sha1",
    ],
}


class CiscoIOSTransport(TransportBase):

    def __init__(self):
        self._session_conn: Optional[AsyncIOSXEDriver] = None

    async def _open_connection(self, connection: ManagementConnection, **kwargs) -> AsyncIOSXEDriver:
        username = kwargs.get("username")
        password = kwargs.get("password")
        if not username or not password:
            raise ValueError("Credentials required: username and password must be provided")
        driver = AsyncIOSXEDriver(
            host=connection.target_ip,
            auth_username=username,
            auth_password=password,
            auth_secondary=kwargs.get("enable_password") or password,
            auth_strict_key=False,
            port=22,
            timeout_socket=30,
            timeout_ops=120,
            transport="asyncssh",
            transport_options={"asyncssh": _LEGACY_ASYNCSSH_OPTIONS},
        )
        await driver.open()
        return driver

    @asynccontextmanager
    async def session(self, connection: ManagementConnection, **kwargs):
        """Hold one SSH session open for the duration of the block."""
        conn = await self._open_connection(connection, **kwargs)
        self._session_conn = conn
        try:
            yield self
        finally:
            self._session_conn = None
            try:
                await conn.close()
            except Exception:
                pass

    @asynccontextmanager
    async def _conn(self, connection: ManagementConnection, **kwargs):
        """Yield active session conn or open a one-shot, closing what we own."""
        if self._session_conn is not None:
            yield self._session_conn
            return
        conn = await self._open_connection(connection, **kwargs)
        try:
            yield conn
        finally:
            try:
                await conn.close()
            except Exception:
                pass

    async def get_config(self, node: NodeListItem, connection: ManagementConnection, **kwargs) -> str:
        async with self._conn(connection, **kwargs) as conn:
            response = await conn.send_command("show running-config", timeout_ops=120)
            return response.result

    async def send_config(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> str:
        async with self._conn(connection, **kwargs) as conn:
            response = await conn.send_configs(commands)
            return response.result

    async def execute(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> list[str]:
        async with self._conn(connection, **kwargs) as conn:
            responses = await conn.send_commands(commands, timeout_ops=120)
            return [r.result for r in responses]

    async def get_lldp_neighbors(self, node: NodeListItem, connection: ManagementConnection, **kwargs) -> list[dict]:
        async with self._conn(connection, **kwargs) as conn:
            neighbors = []
            try:
                response = await conn.send_command("show lldp neighbors detail", timeout_ops=10)
                if "%" not in response.result[:40]:
                    neighbors.extend(self._parse_lldp_detail(response.result))
            except ScrapliTimeout:
                pass
            except Exception:
                pass
            try:
                response = await conn.send_command("show cdp neighbors detail", timeout_ops=10)
                if "%" not in response.result[:40]:
                    seen = {(n["local_interface"], n["remote_device"]) for n in neighbors}
                    for entry in self._parse_cdp_detail(response.result):
                        if (entry["local_interface"], entry["remote_device"]) not in seen:
                            neighbors.append(entry)
            except ScrapliTimeout:
                pass
            except Exception:
                pass
            return neighbors

    @staticmethod
    def _parse_lldp_detail(raw: str) -> list[dict]:
        import re
        entries = re.split(r'-{20,}', raw)
        neighbors = []
        for entry in entries:
            local = re.search(r'Local Intf:\s*(\S+)', entry)
            sys_name = re.search(r'System Name:\s*(\S+)', entry)
            port_id = re.search(r'Port id:\s*(\S+)', entry)
            if local and sys_name:
                neighbors.append({
                    "local_interface": local.group(1),
                    "remote_device": sys_name.group(1),
                    "remote_interface": port_id.group(1) if port_id else "",
                    "discovery_protocol": "lldp",
                })
        return neighbors

    @staticmethod
    def _parse_cdp_detail(raw: str) -> list[dict]:
        import re
        entries = re.split(r'-{20,}', raw)
        neighbors = []
        for entry in entries:
            device = re.search(r'Device ID:\s*(\S+)', entry)
            local = re.search(r'Interface:\s*(\S+?),', entry)
            remote = re.search(r'Port ID.*?:\s*(\S+)', entry)
            if device and local:
                neighbors.append({
                    "local_interface": local.group(1),
                    "remote_device": device.group(1).rstrip('.'),
                    "remote_interface": remote.group(1) if remote else "",
                    "discovery_protocol": "cdp",
                })
        return neighbors


class CiscoIOSCLIDriver(NetworkElementDriver):
    """Cisco IOS CLI driver."""

    renderer_class = CiscoIOSCLIRenderer
    transport_class = CiscoIOSTransport
    parser_class = CiscoIOSCLIParser
    normalizer_class = CiscoIOSNormalizer

    def render(self, configuration: ComposedConfiguration, asset):
        return self.renderer.render(configuration, asset)

    def parse(self, configuration: str) -> ComposedConfiguration:
        return self.parser.parse(configuration)

    def render_patch(self, diff: Diff, node_instance: "NodeInstance"):
        return self.renderer.render_patch(diff, node_instance)

    async def apply_patch(self, diff: Diff, node_instance, node: NodeListItem, connection: ManagementConnection, **kwargs):
        commands = self.render_patch(diff, node_instance=node_instance)
        commands = [c.lstrip() for c in commands.splitlines() if c.strip() != "!"]
        return await self.transport.send_config(node, connection, commands, **kwargs)
