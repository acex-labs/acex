
from contextlib import contextmanager
from typing import Any, Dict, Optional, Callable
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.node_response import NodeListItem
from acex_devkit.models.management_connection import ManagementConnection
from netmiko import ConnectHandler

from acex_devkit.drivers import NetworkElementDriver, TransportBase
from acex_devkit.configdiffer import Diff

from .renderer import CiscoIOSCLIRenderer
from .parser import CiscoIOSCLIParser
from .normalizer import CiscoIOSNormalizer


class CiscoIOSTransport(TransportBase):

    def __init__(self):
        self._session_conn: Optional[ConnectHandler] = None

    def _open_connection(self, connection: ManagementConnection, **kwargs) -> ConnectHandler:
        username = kwargs.get("username")
        password = kwargs.get("password")
        if not username or not password:
            raise ValueError("Credentials required: username and password must be provided")
        device = {
            "device_type": "cisco_ios",
            "host": connection.target_ip,
            "username": username,
            "password": password,
            "secret": kwargs.get("enable_password") or password,
            "port": 22,
            "disabled_algorithms": {},
            "conn_timeout": 30,
        }
        # Allow legacy KEX/ciphers for older IOS devices
        import paramiko
        paramiko.Transport._preferred_kex = (
            "diffie-hellman-group-exchange-sha256",
            "diffie-hellman-group-exchange-sha1",
            "diffie-hellman-group14-sha256",
            "diffie-hellman-group14-sha1",
            "diffie-hellman-group1-sha1",
        )
        conn = ConnectHandler(**device)
        conn.enable()
        return conn

    @contextmanager
    def session(self, connection: ManagementConnection, **kwargs):
        """Hold one SSH session open for the duration of the block."""
        conn = self._open_connection(connection, **kwargs)
        self._session_conn = conn
        try:
            yield self
        finally:
            self._session_conn = None
            try:
                conn.disconnect()
            except Exception:
                pass

    @contextmanager
    def _conn(self, connection: ManagementConnection, **kwargs):
        """Yield active session conn or open a one-shot, closing what we own."""
        if self._session_conn is not None:
            yield self._session_conn
            return
        conn = self._open_connection(connection, **kwargs)
        try:
            yield conn
        finally:
            try:
                conn.disconnect()
            except Exception:
                pass

    def get_config(self, node: NodeListItem, connection: ManagementConnection, **kwargs) -> str:
        with self._conn(connection, **kwargs) as conn:
            return conn.send_command("show running-config", read_timeout=120)

    def send_config(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> str:
        with self._conn(connection, **kwargs) as conn:
            return conn.send_config_set(commands)

    def execute(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> list[str]:
        with self._conn(connection, **kwargs) as conn:
            return [conn.send_command(cmd, read_timeout=120) for cmd in commands]

    def get_lldp_neighbors(self, node: NodeListItem, connection: ManagementConnection, **kwargs) -> list[dict]:
        with self._conn(connection, **kwargs) as conn:
            neighbors = []
            try:
                raw = conn.send_command("show lldp neighbors detail", read_timeout=60)
                neighbors.extend(self._parse_lldp_detail(raw))
            except Exception:
                pass
            try:
                raw = conn.send_command("show cdp neighbors detail", read_timeout=60)
                seen = {(n["local_interface"], n["remote_device"]) for n in neighbors}
                for entry in self._parse_cdp_detail(raw):
                    if (entry["local_interface"], entry["remote_device"]) not in seen:
                        neighbors.append(entry)
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
        config = self.renderer.render(configuration, asset)
        return config

    def parse(self, configuration: str) -> ComposedConfiguration:
        return self.parser.parse(configuration)

    def render_patch(self, diff: Diff, node_instance: "NodeInstance"):
        return self.renderer.render_patch(diff, node_instance)

    def apply_patch(self, diff: Diff, node_instance, node: NodeListItem, connection: ManagementConnection, **kwargs):
        commands = self.render_patch(diff, node_instance=node_instance)
        commands = [c.lstrip() for c in commands.splitlines() if c.strip() != "!"]
        return self.transport.send_config(node, connection, commands, **kwargs)