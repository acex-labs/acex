import re
import threading
from contextlib import contextmanager
from typing import Any

from acex_devkit.configdiffer import Diff
from acex_devkit.drivers import NetworkElementDriver, TransportBase
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.management_connection import ManagementConnection
from acex_devkit.models.node_response import NodeListItem
from netmiko import ConnectHandler

from .parser import FortiOSCLIParser
from .renderer import FortiOSCLIRenderer


class FortiOSTransport(TransportBase):
    def __init__(self):
        self._local = threading.local()

    @property
    def _session_conn(self) -> ConnectHandler | None:
        return getattr(self._local, "conn", None)

    @_session_conn.setter
    def _session_conn(self, value: ConnectHandler | None) -> None:
        self._local.conn = value

    def _open_connection(self, connection: ManagementConnection, **kwargs) -> ConnectHandler:
        username = kwargs.get("username")
        password = kwargs.get("password")
        if not username or not password:
            raise ValueError("Credentials required: username and password must be provided")
        return ConnectHandler(
            device_type="fortinet",
            host=connection.target_ip,
            username=username,
            password=password,
            port=22,
            conn_timeout=30,
        )

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
        """Yield the active session connection, or open a one-shot."""
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
            return conn.send_command("show full-configuration", read_timeout=120)

    def send_config(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> str:
        with self._conn(connection, **kwargs) as conn:
            return conn.send_config_set(commands)

    def execute(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> list[str]:
        with self._conn(connection, **kwargs) as conn:
            return [conn.send_command(cmd, read_timeout=60) for cmd in commands]

    def get_lldp_neighbors(self, node: NodeListItem, connection: ManagementConnection, **kwargs) -> list[dict]:
        with self._conn(connection, **kwargs) as conn:
            try:
                raw = conn.send_command("get system lldp neighbors-detail", read_timeout=30)
            except Exception:
                return []
            return self._parse_lldp_neighbors(raw)

    @staticmethod
    def _parse_lldp_neighbors(raw: str) -> list[dict]:
        neighbors: list[dict] = []
        # Split on the separator between neighbor blocks
        blocks = re.split(r"={3,}", raw)
        for block in blocks:
            local = re.search(r"Interface\s*:\s*(\S+)", block)
            remote_dev = re.search(r"(?:System Name|Neighbor)\s*:\s*(\S+)", block)
            remote_port = re.search(r"Port ID\s*:\s*(\S+)", block)
            if local and remote_dev:
                neighbors.append(
                    {
                        "local_interface": local.group(1),
                        "remote_device": remote_dev.group(1),
                        "remote_interface": remote_port.group(1) if remote_port else "",
                        "discovery_protocol": "lldp",
                    }
                )
        return neighbors


class FortiOSCLIDriver(NetworkElementDriver):
    """Fortinet FortiOS CLI driver."""

    version = "0.1.0"
    renderer_class = FortiOSCLIRenderer
    transport_class = FortiOSTransport
    parser_class = FortiOSCLIParser

    def render(self, configuration: ComposedConfiguration, asset) -> str:
        return self.renderer.render(configuration, asset)

    def parse(self, configuration: str) -> ComposedConfiguration:
        return self.parser.parse(configuration)

    def render_patch(self, diff: Diff, node_instance: Any) -> str:
        return self.renderer.render_patch(diff, node_instance)

    def apply_patch(self, diff: Diff, node_instance, node: NodeListItem, connection: ManagementConnection, **kwargs):
        rendered = self.render_patch(diff, node_instance=node_instance)
        commands = [c.strip() for c in rendered.splitlines() if c.strip()]
        return self.transport.send_config(node, connection, commands, **kwargs)
