from typing import Any

from acex_devkit.configdiffer import Diff
from acex_devkit.drivers import NetworkElementDriver
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.management_connection import ManagementConnection
from acex_devkit.models.node_response import NodeListItem

from acex_driver_cisco_ioscliv2.normalizer.normalizer import CiscoIOSNormalizer
from acex_driver_cisco_ioscliv2.parser.parser import CiscoIOSCLIParser
from acex_driver_cisco_ioscliv2.renderer.renderer import CiscoIOSCLIRenderer
from acex_driver_cisco_ioscliv2.transport.transport import CiscoIOSTransport


class CiscoIOSCLIDriverV2(NetworkElementDriver):
    """Cisco IOS CLI driver."""

    renderer_class = CiscoIOSCLIRenderer
    transport_class = CiscoIOSTransport
    parser_class = CiscoIOSCLIParser
    normalizer_class = CiscoIOSNormalizer

    def render(self, configuration: ComposedConfiguration, asset):
        return self.renderer.render(configuration, asset)

    def parse(self, configuration: str) -> ComposedConfiguration:
        return self.parser.parse(configuration)

    def render_patch(self, diff: Diff, node_instance: Any):
        return self.renderer.render_patch(diff, node_instance)

    async def apply_patch(
        self, diff: Diff, node_instance, node: NodeListItem, connection: ManagementConnection, **kwargs
    ):
        commands = self.render_patch(diff, node_instance=node_instance)
        commands = [c.lstrip() for c in commands.splitlines() if c.strip() != "!"]
        return await self.transport.send_config(node, connection, commands, **kwargs)
