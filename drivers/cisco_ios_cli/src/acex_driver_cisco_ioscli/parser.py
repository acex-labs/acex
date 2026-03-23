#from acex.models.composed_configuration import ComposedConfiguration, EthernetCsmacdInterface, L3IpvlanInterface, SoftwareLoopbackInterface, Ieee8023adLagInterface
from acex_devkit.models.composed_configuration import (
    ComposedConfiguration,
    EthernetCsmacdInterface,
    L3IpvlanInterface,
    SoftwareLoopbackInterface,
    Ieee8023adLagInterface,
    SshServer,
    NtpServer,
    SystemConfig,
    ReferenceTo,
)
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

    # Mostly used to remove metadata key, which contains non-serializable data and is not needed in the final output, but can be used to remove any key if needed in the future
    def removekey(self, d, key):
        if hasattr(d, 'model_dump'): # Pydantic v2
            r = d.model_dump()
            #print('model_dump: ', r)
        elif hasattr(d, 'dict'): # Pydantic v1
            r = d.dict()
            #print('dict: ', r)
        else:
            r = dict(d) # Fallback for regular dicts or other types
            #print('dict fallback: ', r)

        def _remove(obj):
            if isinstance(obj, dict):
                #print('removing key from dict: ', obj)
                return {k: _remove(v) for k, v in obj.items() if k != key}
            elif isinstance(obj, list): # supporting in case we use lists of dicts in the future
                #print('removing key from list: ', obj)
                return [_remove(item) for item in obj]
            #print('returning obj: ', obj)
            return obj

        return _remove(r)

    def parse(self, configuration: str) -> dict:
        """Parse the Cisco IOS CLI configuration content."""
        self.running_config = configuration
        self.parse_system_settings()
        self.parse_interfaces()
        self.parse_l3_interfaces()
        self.parse_ntp()
        self.parse_ssh()

        return self._parsed_config

    def parse_l3_interfaces(self):
        """Parse L3 interfaces."""
        command = "show running svi interfaces"
    
        parsed_data = parse_output(
            platform=self.platform,
            template_dir=self.custom_templates_dir,
            command=command,
            data=self.running_config
        )

        for intf in parsed_data:
            intf["enabled"] = map_enabled(intf.get("ENABLED", ""))
            intf['description'] = intf.get('description') or None
            intf['ipv4'] = intf.get('ipv4_address') or None
            #intf['ipv6_address'] = intf.get('ipv6_address') or None
            intf['vlan_id'] = int(intf['name'].replace('Vlan',''))

        interfaces_dict = {
            intf['name']: self.removekey(L3IpvlanInterface(index=index, **intf), 'metadata')
            for index, intf in enumerate(parsed_data)
        }

        self.parsed_config.interfaces.update(interfaces_dict)

    def parse_interfaces(self) -> None:
        """Parse physical interfaces."""
        command = "show running physical interfaces"

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
                    #vlans = [i for i in range(1, 4095)]
                    vlans = list()
                else:
                    vlans = expand_vlans(intf["trunk_allowed_vlans"])
                intf["trunk_allowed_vlans"] = vlans
            else:
                intf["trunk_allowed_vlans"] = None

            intf['native_vlan'] = int(intf['native_vlan']) if intf.get('native_vlan') else None
            intf['access_vlan'] = int(intf['access_vlan']) if intf.get('access_vlan') else None
            intf['voice_vlan'] = int(intf['voice_vlan']) if intf.get('voice_vlan') else None

            if intf["switchport_mode"]:
                switchport = True
                switchport_mode = intf["switchport_mode"]
            else:
                switchport = False
                switchport_mode = 'access'
            intf["switchport"] = switchport
            intf["switchport_mode"] = switchport_mode

            intf['description'] = intf.get('description') or None
            intf['negotiation'] = True if intf.get('negotiation') else False

        interfaces_dict = {
            intf['name']: self.removekey(EthernetCsmacdInterface(index=index, **intf), 'metadata')
            for index, intf in enumerate(parsed_data)
        }
        self.parsed_config.interfaces.update(interfaces_dict)

    def parse_lag_interfaces(self) -> None:
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
            intf['name']: self.removekey(Ieee8023adLagInterface(index=index, **intf), 'metadata')
            for index, intf in enumerate(parsed_data)
        }
        self.parsed_config.interfaces.update(interfaces_dict)

    def parse_system_settings(self) -> None:
        """Parse the system hostname from the configuration content."""
        command = "show running system"

        parsed_data = parse_output(
            platform=self.platform,
            template_dir=self.custom_templates_dir,
            command=command,
            data=self.running_config
        )

        system_settings = {}

        #hostname
        system_settings['hostname'] = parsed_data[0].get("hostname") if parsed_data[0].get("hostname") else None
        #banner motd
        system_settings['motd_banner'] = ' '.join(parsed_data[0].get("banner_motd")) if parsed_data[0].get("banner_motd") else None
        
        #banner login
        system_settings['login_banner'] = ' '.join(parsed_data[0].get("banner_login")) if parsed_data[0].get("banner_login") else None
        
        #domain_name
        system_settings['domain_name'] = parsed_data[0].get("domain_name") if parsed_data[0].get("domain_name") else None
        #location (from snmp)
        system_settings['location'] = parsed_data[0].get("location") if parsed_data[0].get("location") else None
        #contact (from snmp)
        system_settings['contact'] = parsed_data[0].get("contact") if parsed_data[0].get("contact") else None

        self.parsed_config.system.config = self.removekey(SystemConfig(**system_settings), 'metadata')

    def parse_ntp(self) -> None:
        """Parse NTP configuration."""
        command = "show running ntp"

        parsed_data = parse_output(
            platform=self.platform,
            template_dir=self.custom_templates_dir,
            command=command,
            data=self.running_config
        )

        ntp_servers = {}
        for ntp_server in parsed_data:
            if not ntp_server.get("address"):
                continue
            else:
                ntp_server['address'] = str(ntp_server.get("address"))

            ntp_server['version'] = int(ntp_server['version']) if ntp_server.get('version') else None

            ## Not used in Cisco IOS, but included for completeness
            ##port = entry.get("port")
            ##if port:
            ##    ntp_server["port"] = {"value": int(port)}

            if ntp_server.get("prefer"):
                ntp_server["prefer"] = True
            else:
                ntp_server["prefer"] = False

            if ntp_server.get("source_interface"):
                for intf_name, intf in self.parsed_config.interfaces.items():
                    intf_type = intf.get('type') if isinstance(intf, dict) else getattr(intf, 'type', None)
                    intf_vlan_id = intf.get('vlan_id') if isinstance(intf, dict) else getattr(intf, 'vlan_id', None)
                    if intf_type == 'l3ipvlan' and intf_vlan_id == int(ntp_server.get("source_interface").replace('Vlan','')):
                        intf_ref = ReferenceTo(pointer=f"interfaces.{intf_name}")
                        break
                ntp_server['source_interface'] = intf_ref
            ntp_servers[ntp_server['address']] = self.removekey(NtpServer(**ntp_server), 'metadata')

        self.parsed_config.system.ntp.servers = ntp_servers

    def parse_ssh(self) -> None:
        """Parse SSH configuration."""
        command = "show running ssh"

        parsed_data = parse_output(
            platform=self.platform,
            template_dir=self.custom_templates_dir,
            command=command,
            data=self.running_config
        )
    
        ssh_values_dict = dict()
        for entry in parsed_data:
            ssh_version = None
            if entry.get("protocol_version"):
                ssh_version = {"value": entry.get("protocol_version")}
                ssh_values_dict['enable'] = {"value": bool(ssh_version)}
                ssh_values_dict['protocol_version'] = ssh_version

            ssh_timeout = None
            if entry.get("timeout"):
                ssh_timeout = {"value": entry.get("timeout")}
                ssh_values_dict['timeout'] = ssh_timeout

            ssh_auth_retries = None
            if entry.get("authentication_retries"):
                ssh_auth_retries = {"value": entry.get("authentication_retries")}
                ssh_values_dict['authentication_retries'] = ssh_auth_retries

            if entry.get("source_interface"):
                for intf_name, intf in self.parsed_config.interfaces.items():
                    intf_type = intf.get('type') if isinstance(intf, dict) else getattr(intf, 'type', None)
                    intf_vlan_id = intf.get('vlan_id') if isinstance(intf, dict) else getattr(intf, 'vlan_id', None)
                    if intf_type == 'l3ipvlan' and intf_vlan_id == int(entry.get("source_interface").replace('Vlan','')):
                        intf_ref = ReferenceTo(pointer=f"interfaces.{intf_name}")
                        break
                ssh_values_dict['source_interface'] = intf_ref

        self.parsed_config.system.ssh.config = self.removekey(SshServer(**ssh_values_dict), 'metadata')
        algorithm_list = []
        self.parsed_config.system.ssh.host_keys = {
            "algorithms": algorithm_list,
            "public_keys": {}
        }