
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

    def _get_connection(self, connection: ManagementConnection, **kwargs) -> ConnectHandler:
        device = {
            "device_type": "cisco_ios",
            "host": connection.target_ip,
            "username": kwargs.get("username"),
            "password": kwargs.get("password"),
            "port": 22,
            "disabled_algorithms": {},
            "conn_timeout": 30,
        }
        if not device["username"] or not device["password"]:
            raise ValueError("Credentials required: username and password must be provided")
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
        enable_pw = kwargs.get("enable_password")
        if enable_pw:
            conn.enable(cmd="enable", pattern="ssword", enable_pattern=r"#")
            conn.send_command_timing(enable_pw)
        else:
            conn.enable()
        return conn

    def get_config(self, node: NodeListItem, connection: ManagementConnection, **kwargs) -> str:
        conn = self._get_connection(connection, **kwargs)
        try:
            return conn.send_command("show running-config", read_timeout=120)
        finally:
            conn.disconnect()

    def send_config(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> str:
        conn = self._get_connection(connection, **kwargs)
        try:
            return conn.send_config_set(commands)
        finally:
            conn.disconnect()

    def execute(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> list[str]:
        conn = self._get_connection(connection, **kwargs)
        try:
            return [conn.send_command(cmd, read_timeout=120) for cmd in commands]
        finally:
            conn.disconnect()

    def get_lldp_neighbors(self, node: NodeListItem, connection: ManagementConnection, **kwargs) -> list[dict]:
        conn = self._get_connection(connection, **kwargs)
        try:
            neighbors = []
            # LLDP first (preferred)
            try:
                raw = conn.send_command("show lldp neighbors detail", read_timeout=60)
                neighbors.extend(self._parse_lldp_detail(raw))
            except Exception:
                pass
            # CDP — only add links not already seen via LLDP
            try:
                raw = conn.send_command("show cdp neighbors detail", read_timeout=60)
                seen = {(n["local_interface"], n["remote_device"]) for n in neighbors}
                for entry in self._parse_cdp_detail(raw):
                    if (entry["local_interface"], entry["remote_device"]) not in seen:
                        neighbors.append(entry)
            except Exception:
                pass
            return neighbors
        finally:
            conn.disconnect()

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