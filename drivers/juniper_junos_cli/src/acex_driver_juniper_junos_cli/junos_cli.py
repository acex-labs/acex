
from contextlib import contextmanager
from typing import Optional
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.node_response import NodeListItem
from acex_devkit.models.management_connection import ManagementConnection
from netmiko import ConnectHandler

from acex_devkit.drivers import NetworkElementDriver, TransportBase
from acex_devkit.configdiffer import Diff

from .renderer import JunosCLIRenderer
from .parser import JunosCLIParser


class JunosCLITransport(TransportBase):

    def __init__(self):
        self._session_conn: Optional[ConnectHandler] = None

    def _open_connection(self, connection: ManagementConnection, **kwargs) -> ConnectHandler:
        username = kwargs.get("username")
        password = kwargs.get("password")
        if not username or not password:
            raise ValueError("Credentials required: username and password must be provided")
        device = {
            "device_type": "juniper_junos",
            "host": connection.target_ip,
            "username": username,
            "password": password,
            "port": 22,
            "conn_timeout": 30,
        }
        return ConnectHandler(**device)

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
            # `display set` flattens hierarchical config into reproducible
            # `set` lines; `no-more` disables paging.
            return conn.send_command(
                "show configuration | display set | no-more",
                read_timeout=120,
            )

    def send_config(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> str:
        # netmiko's juniper_junos handler enters configure mode, sends the
        # commands, commits, and exits — driven by send_config_set.
        with self._conn(connection, **kwargs) as conn:
            return conn.send_config_set(commands)

    def execute(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> list[str]:
        with self._conn(connection, **kwargs) as conn:
            return [conn.send_command(cmd, read_timeout=120) for cmd in commands]

    def get_lldp_neighbors(self, node: NodeListItem, connection: ManagementConnection, **kwargs) -> list[dict]:
        with self._conn(connection, **kwargs) as conn:
            try:
                raw = conn.send_command("show lldp neighbors", read_timeout=60)
            except Exception:
                return []
            return self._parse_lldp_table(raw)

    @staticmethod
    def _parse_lldp_table(raw: str) -> list[dict]:
        # `show lldp neighbors` returns a fixed-width table:
        # Local Interface  Parent Interface  Chassis Id         Port info  System Name
        # ge-0/0/0         -                 00:11:22:33:44:55  ge-0/0/1   peer-switch
        neighbors = []
        lines = [ln.rstrip() for ln in raw.splitlines() if ln.strip()]
        # Skip header line if present
        for line in lines:
            if line.lower().startswith("local interface"):
                continue
            parts = line.split()
            # Expected at minimum: local, parent, chassis_id, port_id, sysname
            if len(parts) < 5:
                continue
            local_iface = parts[0]
            remote_port = parts[-2]
            remote_dev = parts[-1]
            neighbors.append({
                "local_interface": local_iface,
                "remote_device": remote_dev,
                "remote_interface": remote_port,
                "discovery_protocol": "lldp",
            })
        return neighbors


class JunosCLI(NetworkElementDriver):
    """Juniper Junos CLI driver."""

    version = "1.0.0"
    renderer_class = JunosCLIRenderer
    transport_class = JunosCLITransport
    parser_class = JunosCLIParser

    def render(self, configuration: ComposedConfiguration, asset):
        return self.renderer.render(configuration, asset)

    def parse(self, configuration: str) -> ComposedConfiguration:
        return self.parser.parse(configuration)

    def render_patch(self, diff: Diff, node_instance: "NodeInstance"):
        return self.renderer.render_patch(diff, node_instance)

    def apply_patch(self, diff: Diff, node_instance, node: NodeListItem, connection: ManagementConnection, **kwargs):
        rendered = self.render_patch(diff, node_instance=node_instance)
        commands = [c.strip() for c in rendered.splitlines() if c.strip()]
        return self.transport.send_config(node, connection, commands, **kwargs)
