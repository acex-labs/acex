#from acex.models.composed_configuration import ComposedConfiguration, EthernetCsmacdInterface, L3IpvlanInterface, SoftwareLoopbackInterface, Ieee8023adLagInterface
from acex_devkit.models.composed_configuration import (
    ComposedConfiguration,
    EthernetCsmacdInterface,
    L3IpvlanInterface,
    SoftwareLoopbackInterface,
    Ieee8023adLagInterface,
    ReferenceTo
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

    def removekey(self, d, key):
        r = dict(d)
        #print('r: ', r)
        #for k, v in r.items():
            #print('k: ', k, 'v: ', v)
            #print('k type: ', type(k), 'v type: ', type(v))
        #for k, v in r.items():
        #    if isinstance(v, dict):
        #        r[k] = self.removekey(v, key)
        if key in r:
            del r[key]
        return r

    def gen_dict_extract(self, key, var):
        if hasattr(var,'items'): # hasattr(var,'items') for python 3
            for k, v in var.items(): # var.items() for python 3
                if k == key:
                    yield v
                if isinstance(v, dict):
                    for result in self.gen_dict_extract(key, v):
                        yield result
                elif isinstance(v, list):
                    for d in v:
                        for result in self.gen_dict_extract(key, d):
                            yield result

    def parse(self, configuration: str) -> dict:
        """Parse the Cisco IOS CLI configuration content."""
        self.running_config = configuration
        self.parse_system_hostname()
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

    def parse_interfaces(self):
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
            intf['name']: EthernetCsmacdInterface(index=index, **intf)
            for index, intf in enumerate(parsed_data)
        }
        self.parsed_config.interfaces.update(interfaces_dict)

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

    def parse_ntp(self) -> str:
        """Parse NTP configuration."""
        command = "show running ntp"

        parsed_data = parse_output(
            platform=self.platform,
            template_dir=self.custom_templates_dir,
            command=command,
            data=self.running_config
        )

        ntp_servers = {}
        for entry in parsed_data:
            server = entry.get("server")
            if not server:
                continue

            ntp_server = {
                "address": {"value": server}
            }

            version = entry.get("version")
            if version:
                ntp_server["version"] = {"value": int(version)}

            # Not used in Cisco IOS, but included for completeness
            #port = entry.get("port")
            #if port:
            #    ntp_server["port"] = {"value": int(port)}

            prefer = entry.get("prefer")
            if prefer:
                ntp_server["prefer"] = {"value": True}

            source_interface = entry.get("source_interface")
            if source_interface:
                ntp_server["source_interface"] = {"value": source_interface}
                
            ntp_servers[server] = ntp_server

        self.parsed_config.system.ntp.config = {
            "enabled": {"value": bool(ntp_servers)}
        }
        self.parsed_config.system.ntp.servers = ntp_servers

    def parse_ssh(self) -> str:
        """Parse SSH configuration."""
        command = "show running ssh"

        #print(self.running_config)
        #print("parsed_config: ",self._parsed_config)

        parsed_data = parse_output(
            platform=self.platform,
            template_dir=self.custom_templates_dir,
            command=command,
            data=self.running_config
        )
    
        ssh_values_dict = dict()
        #print(f"Parsed SSH data: {parsed_data}")
        for entry in parsed_data:
            #print(f"Parsing SSH entry: {entry}")
            ssh_version = None
            if entry.get("protocol_version"):
                ssh_version = {"value": entry.get("protocol_version")}
                ssh_values_dict['enabled'] = {"value": bool(ssh_version)}
                ssh_values_dict['protocol_version'] = ssh_version

            ssh_timeout = None
            if entry.get("timeout"):
                ssh_timeout = {"value": entry.get("timeout")}
                ssh_values_dict['timeout'] = ssh_timeout

            ssh_auth_retries = None
            if entry.get("authentication_retries"):
                ssh_auth_retries = {"value": entry.get("authentication_retries")}
                ssh_values_dict['authentication_retries'] = ssh_auth_retries

            ssh_source_interface = None
            if entry.get("source_interface"):
                for intf_name, intf in self.parsed_config.interfaces.items():
                    intf_type = intf.get('type') if isinstance(intf, dict) else getattr(intf, 'type', None)
                    intf_vlan_id = intf.get('vlan_id') if isinstance(intf, dict) else getattr(intf, 'vlan_id', None)
                    if intf_type == 'l3ipvlan' and intf_vlan_id == int(entry.get("source_interface").replace('Vlan','')):
                        intf_ref = ReferenceTo(pointer=f"interfaces.{intf_name}")
                        break
                #ssh_source_interface = {"value": entry.get("source_interface")}
                #ptr_src_int = ''
                # Här i parsed interfaces finns det source_interface jag letar efter
                # Sedan behöver en referens göras som säger "interfaces.x.y.vlan2" där finns all info om interfacet
                #if config.interfaces.interface1.index == 2:
                #    nånting med vlan2 här
                #   använd ReferenceTo klassen här när du skpar source interface referensen till ex. vlan2
                # parsed_config.interfaces.interface1.name = "Vlan2"
                #ssh_source_interface = {"pointer" : ptr_src_int} #vlan2
                ssh_values_dict['source_interface'] = intf_ref

            #ssh_values_dict = {
            #    "enabled": {"value": bool(ssh_version)},
            #    "protocol_version": ssh_version,
            #    "timeout": ssh_timeout,
            #    "authentication_retries": ssh_auth_retries,
            #    "source_interface": ssh_source_interface
            #}

            #print(f"SSH values dict: {ssh_values_dict}")

            #self.parsed_config.system.ssh.config = {
            #    "enabled": {"value": bool(ssh_version)},
            #    "protocol_version": ssh_version,
            #    "timeout": ssh_timeout,
            #    "authentication_retries": ssh_auth_retries,
            #    "source_interface": ssh_source_interface
            #}
        self.parsed_config.system.ssh.config = ssh_values_dict

        algorithm_list = []
        self.parsed_config.system.ssh.host_keys = {
            "algorithms": algorithm_list,
            "public_keys": {}
        }

        #print('='*100)
        #print("Final parsed SSH config: ", self.parsed_config.system.ssh.config)
        #print('='*100)