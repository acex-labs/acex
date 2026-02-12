from acex.models.composed_configuration import ComposedConfiguration, EthernetCsmacdInterface, L3IpvlanInterface, SoftwareLoopbackInterface, Ieee8023adLagInterface
from ntc_templates.parse import parse_output
import os

def map_enabled(enabled_value: str) -> bool:
    """
    Map TextFSM 'ENABLED' field to boolean.
    True = interface is up (no shutdown or empty)
    False = interface is shutdown
    """
    return enabled_value != "shutdown"

def expand_vlans(vlan_str: str) -> list[int]:
    """
    Expand VLAN string representation to a list of integers.
    E.g., "1-3,5" -> [1, 2, 3, 5]
    """
    vlans = set()
    for part in vlan_str.split(','):
        if '-' in part:
            start, end = map(int, part.split('-'))
            vlans.update(range(start, end + 1))
        else:
            vlans.add(int(part))
    return sorted(vlans)


class CiscoIOSCLIParser:
    def __init__(self):
        self.running_config = None
        self._parsed_config = ComposedConfiguration()

    @property
    def parsed_config(self):
        """Return the model class for the parser."""
        return self._parsed_config

    @property
    def custom_templates_dir(self) -> str:
        """Return the directory path for custom TextFSM templates."""
        package_dir = os.path.dirname(__file__)
        return os.path.join(package_dir, "custom_textfsm_templates")

    @property
    def platform(self) -> str:
        """Return the platform name for the parser."""
        return "cisco_ios"

    def parse(self, configuration: str) -> dict:
        """Parse the Cisco IOS CLI configuration content."""
        self.running_config = configuration
        self.parse_system_hostname()
        return self._parsed_config

    def parse_lag_interfaces(self) -> Ieee8023adLagInterface:
        """Parse LAG interfaces."""
        command = "show running lag interfaces"

        parsed_data = parse_output(
            platform=self.platform,
            template_dir=self.custom_templates_dir,
            command=command,
            data=self.running_config
        )
        for intf in parsed_data:
            intf["enabled"] = map_enabled(intf.get("ENABLED", ""))
            if intf["switchport_mode"] == "trunk":
                if not intf["trunk_allowed_vlans"]:
                    vlans = [i for i in range(1, 4095)]
                else:
                    vlans = expand_vlans(intf["trunk_allowed_vlans"])
                intf["trunk_allowed_vlans"] = vlans

            if intf["switchport_mode"]:
                switchport = True
            else:
                switchport = False
            intf["switchport"] = switchport

        interfaces_dict = {
            intf['name']: Ieee8023adLagInterface(index=index, **intf)
            for index, intf in enumerate(parsed_data)
        }
        self.parsed_config.interfaces.update(interfaces_dict)

    def parse_system_hostname(self) -> str:
        """Parse the system hostname from the configuration content."""
        command = "show running hostname"

        parsed_data = parse_output(
            platform=self.platform,
            template_dir=self.custom_templates_dir,
            command=command,
            data=self.running_config
        )
        self.parsed_config.system.config.hostname = {
            "value": parsed_data[0].get("hostname")
            }
