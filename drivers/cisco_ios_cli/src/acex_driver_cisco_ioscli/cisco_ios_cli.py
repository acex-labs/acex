
from typing import Any, Dict, Optional, Callable
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.node_response import NodeListItem
from acex_devkit.models.management_connection import ManagementConnection
from netmiko import ConnectHandler

from acex_devkit.drivers import NetworkElementDriver, TransportBase
from acex_devkit.configdiffer import Diff

from .renderer import CiscoIOSCLIRenderer
from .parser import CiscoIOSCLIParser


class CiscoIOSTransport(TransportBase):

    def _get_connection(self, connection: ManagementConnection) -> ConnectHandler:
        device = {
            "device_type": "cisco_ios",
            "host": connection.target_ip,
            "username": "admin",
            "password": "polly123",
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

    def get_config(self, node: NodeListItem, connection: ManagementConnection, **kwargs) -> str:
        conn = self._get_connection(connection)
        try:
            return conn.send_command("show running-config")
        finally:
            conn.disconnect()

    def send_config(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> str:
        conn = self._get_connection(connection)
        try:
            return conn.send_config_set(commands)
        finally:
            conn.disconnect()

    def execute(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> list[str]:
        conn = self._get_connection(connection)
        try:
            return [conn.send_command(cmd) for cmd in commands]
        finally:
            conn.disconnect()


class CiscoIOSCLIDriver(NetworkElementDriver):
    """Cisco IOS CLI driver."""

    renderer_class = CiscoIOSCLIRenderer
    transport_class = CiscoIOSTransport
    parser_class = CiscoIOSCLIParser

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