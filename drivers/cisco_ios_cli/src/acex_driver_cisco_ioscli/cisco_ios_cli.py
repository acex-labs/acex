
from typing import Any, Dict, Optional
from acex.models.composed_configuration import ComposedConfiguration
from acex.plugins.neds.core import NetworkElementDriver, TransportBase
import difflib

from acex_devkit.drivers import NetworkElementDriver
from acex_devkit.configdiffer import Diff

from .renderer import CiscoIOSCLIRenderer
from .parser import CiscoIOSCLIParser


class CiscoIOSTransport(TransportBase):
    def connect(self) -> None:
        """Connect to the Cisco IOS CLI device."""
        # Implement connection logic
        pass

    def send(self, payload: Any) -> None:
        """Send the rendered configuration to the device."""
        # Implement sending logic
        pass

    def verify(self) -> bool:
        """Verify the configuration on the device."""
        # Implement verification logic
        return True

    def rollback(self) -> None:
        """Rollback the configuration if verification fails."""
        # Implement rollback logic
        pass


class CiscoIOSCLIDriver(NetworkElementDriver):
    """Cisco IOS CLI driver."""

    renderer_class = CiscoIOSCLIRenderer
    transport_class = CiscoIOSTransport
    parser_class = CiscoIOSCLIParser

    def render(self, configuration: ComposedConfiguration, asset):
        """Render the configuration for a Cisco IOS CLI device."""
        # Call the base class render method
        config = self.renderer.render(configuration, asset)
        return config

    def parse(self, configuration: str) -> ComposedConfiguration: 
        return self.parser.parse(configuration)

    def jusify_diff_commands(
        self, 
        configuration: ComposedConfiguration, 
        diff: Diff,
        asset: "Asset"
        ):
        """
        TODO: Find a good name for this method
        """ 
        from acex_devkit.configdiffer import ConfigDiffer

        # Create a new config by applying the diff
        differ = ConfigDiffer()
        new_config = differ.apply_diff(configuration, diff)

        # Render both: 
        original_config = self.render(configuration, asset)
        new_config = self.render(new_config, asset)

        # diff
        old_lines = original_config.splitlines()
        new_lines = new_config.splitlines()
        
        differ = difflib.Differ()
        diff = list(differ.compare(old_lines, new_lines))
        
        # Convert diff to CLI commands
        commands = self._diff_to_cli_commands(diff)
        
        return "\n".join(commands)
    
    def _diff_to_cli_commands(self, diff_lines: list[str]) -> list[str]:
        """
        Convert diff output to Cisco CLI commands.
        Lines starting with '- ' become 'no <command>'
        Lines starting with '+ ' become '<command>'
        """
        commands = []
        
        for line in diff_lines:
            if line.startswith('- '):
                # Removed line - add 'no' prefix
                cmd = line[2:].strip()
                if cmd and not cmd.startswith('!'):  # Skip empty lines and comments
                    commands.append(f"no {cmd}")
            elif line.startswith('+ '):
                # Added line - use as-is
                cmd = line[2:].strip()
                if cmd and not cmd.startswith('!'):  # Skip empty lines and comments
                    commands.append(cmd)
        
        return commands
