#from acex.models.composed_configuration import ComposedConfiguration, EthernetCsmacdInterface, L3IpvlanInterface, SoftwareLoopbackInterface, Ieee8023adLagInterface
from acex_devkit.models.composed_configuration import (
    AuthorizedKey,
    AuthorizedKeyAlgorithms,
    ComposedConfiguration,
    EthernetCsmacdInterface, 
    L3IpvlanInterface,
    SoftwareLoopbackInterface,
    Ieee8023adLagInterface,
    SshServer,
    NtpServer,
    SystemConfig,
    SnmpConfig,
    SnmpCommunity,
    SnmpUser,
    SnmpServer,
    TrapEvent,
    SnmpView,
    SnmpSecurityLevel,
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
        self.parse_snmp()
        self.parse_snmp_servers()
        self.parse_snmp_views()
        self.parse_snmp_communities()
        self.parse_snmp_users()


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
                    vlans = None
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
                    vlans = None
                else:
                    vlans = expand_vlans(intf["trunk_allowed_vlans"])
                intf["trunk_allowed_vlans"] = vlans
            else:
                intf["trunk_allowed_vlans"] = None

            intf['native_vlan'] = int(intf['native_vlan']) if intf.get('native_vlan') else None
            intf['access_vlan'] = int(intf['access_vlan']) if intf.get('access_vlan') else None

            if intf["switchport_mode"]:
                switchport = True
                switchport_mode = intf["switchport_mode"]
            else:
                switchport = False
                switchport_mode = 'access'
            intf["switchport"] = switchport
            intf["switchport_mode"] = switchport_mode

            intf['description'] = intf.get('description') or None

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
                    intf_vlan_id = intf['vlan_id'].get('value') if isinstance(intf, dict) and intf.get('vlan_id') else getattr(intf, 'vlan_id', None)
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
                    intf_vlan_id = intf['vlan_id'].get('value') if isinstance(intf, dict) and intf.get('vlan_id') else getattr(intf, 'vlan_id', None)
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

    # Only used for local testing with static config file
    def load_running_config(self, filepath: str) -> str:
        with open(filepath, 'r') as f:
            return f.read()

    def parse_snmp_traps(self) -> None:
        """Parse SNMP trap configuration."""
        command = "show running snmp traps"

        parsed_data = parse_output(
            platform=self.platform,
            template_dir=self.custom_templates_dir,
            command=command,
            data=self.running_config
        )

        snmp_traps_dict = {}
        for entry in parsed_data:
            snmp_trap_values_dict = {}
            # Every trap that is allowed is specified in TrapEvent model, so we loop through all traps and check if they are enabled, if they are enabled we add them to the trap_events list in the SnmpConfig
            # Below code needs to be fixed and handled correctly as the config that Cisco gives does not match exactly how the traps are defined in the model.
            if entry.get('traps'):
                for i, trap in enumerate(entry.get('traps')):
                    snmp_trap_values_dict['name'] = f"trap_{i}"
                    snmp_trap_values_dict['event_name'] = trap
                    snmp_traps_dict[entry.get('event_name')] = self.removekey(TrapEvent(**snmp_trap_values_dict), 'metadata')

        self.parsed_config.system.snmp.trap_events = snmp_traps_dict    

    def parse_snmp_views(self) -> None:
        """Parse SNMP view configuration."""
        command = "show running snmp views"

        parsed_data = parse_output(
            platform=self.platform,
            template_dir=self.custom_templates_dir,
            command=command,
            data=self.running_config
        )

        snmp_views_dict = {}
        for i, entry in enumerate(parsed_data):
            snmp_view_values_dict = {}
            if entry.get("view_name"):
                snmp_view_values_dict['name'] = f"{entry.get('view_name')}_{i}" if entry.get("view_name") else None
                snmp_view_values_dict['oid'] = entry.get("view_oid") if entry.get("view_oid") else None
                snmp_view_values_dict['included'] = True if 'included' in entry.get("view_status") else False
                snmp_views_dict[f"{entry.get('view_name')}_{i}"] = self.removekey(SnmpView(**snmp_view_values_dict), 'metadata')
        
        self.parsed_config.system.snmp.views = snmp_views_dict

    def parse_snmp_servers(self) -> None:
        """Parse SNMP server configuration."""
        command = "show running snmp servers"

        parsed_data = parse_output(
            platform=self.platform,
            template_dir=self.custom_templates_dir,
            command=command,
            data=self.running_config
        )

        snmp_servers_dict = {}
        for entry in parsed_data:
            snmp_server_values_dict = {}
            snmp_server_values_dict['address'] = entry.get("host") 
            if entry.get("host"):
                snmp_server_values_dict['address'] = str(entry.get("host"))
                snmp_server_values_dict['enabled'] = True
            else:
                snmp_server_values_dict['address'] = None
                snmp_server_values_dict['enabled'] = False
            snmp_server_values_dict['port'] = int(entry.get("server_port")) if entry.get("server_port") else None
            if entry.get("version"):
                version = 'v3' if entry.get("version") == '3' else 'v2c' if entry.get("version") == '2c' else None
                snmp_server_values_dict['version'] = version
            snmp_server_values_dict['community'] = entry.get("community_string") if entry.get("community_string") else None
            snmp_server_values_dict['username'] = entry.get("server_user") if entry.get("server_user") else None
            snmp_server_values_dict['security_level'] = entry.get("server_security_level") if entry.get("server_security_level") else None
            if entry.get("source_interface"):
                for intf_name, intf in self.parsed_config.interfaces.items():
                    intf_type = intf.get('type') if isinstance(intf, dict) else getattr(intf, 'type', None)
                    intf_vlan_id = intf['vlan_id'].get('value') if isinstance(intf, dict) and intf.get('vlan_id') else getattr(intf, 'vlan_id', None)
                    if intf_type == 'l3ipvlan' and intf_vlan_id == int(entry.get("source_interface").replace('Vlan','')):
                        intf_ref = ReferenceTo(pointer=f"interfaces.{intf_name}")
                        snmp_server_values_dict['source_interface'] = intf_ref
                        break
                    else:
                        snmp_server_values_dict['source_interface'] = None
            snmp_server_values_dict['network_instance'] = entry.get("vrf") if entry.get("vrf") else None

            snmp_servers_dict[entry.get('host')] = self.removekey(SnmpServer(**snmp_server_values_dict), 'metadata')

        self.parsed_config.system.snmp.trap_servers = snmp_servers_dict

    def parse_snmp_users(self) -> None:
        """Parse SNMP user configuration."""
        command = "show running snmp users"

        parsed_data = parse_output(
            platform=self.platform,
            template_dir=self.custom_templates_dir,
            command=command,
            data=self.running_config
        )

        snmp_users_dict = {}
        for i, entry in enumerate(parsed_data):
            snmp_user_values_dict = {}
            snmp_user_values_dict['name'] = f'user_{i}'
            snmp_user_values_dict['username'] = entry.get("user") if entry.get("user") else None
            # Security levels
            #   auth    group using the authNoPriv Security Level
            #   noauth  group using the noAuthNoPriv Security Level
            #   priv    group using SNMPv3 authPriv security level
            if entry.get("security_level") == "auth":
                snmp_user_values_dict['security_level'] = "AUTH_NO_PRIV"
            elif entry.get("security_level") == "noauth":
                snmp_user_values_dict['security_level'] = "NO_AUTH_NO_PRIV"
            elif entry.get("security_level") == "priv":
                snmp_user_values_dict['security_level'] = "AUTH_PRIV"
            else:
                None
            snmp_user_values_dict['auth_protocol'] = entry.get("auth_protocol") if entry.get("auth_protocol") else None
            snmp_user_values_dict['auth_password'] = entry.get("auth_password") if entry.get("auth_password") else None
            snmp_user_values_dict['priv_protocol'] = entry.get("priv_protocol") if entry.get("priv_protocol") else None
            snmp_user_values_dict['priv_password'] = entry.get("priv_password") if entry.get("priv_password") else None

            snmp_users_dict[f'user_{i}'] = self.removekey(SnmpUser(**snmp_user_values_dict), 'metadata')

        self.parsed_config.system.snmp.users = snmp_users_dict

    def parse_snmp_communities(self) -> None:
        """Parse SNMP community configuration."""
        command = "show running snmp communities"

        parsed_data = parse_output(
            platform=self.platform,
            template_dir=self.custom_templates_dir,
            command=command,
            data=self.running_config
        )

        snmp_communities_dict = {}
        for i, entry in enumerate(parsed_data):
            snmp_community_values_dict = {}
            snmp_community_values_dict['name'] = f'community_{i}'
            snmp_community_values_dict['community'] = entry.get("community_string") if entry.get("community_string") else None
            snmp_community_values_dict['access'] = entry.get("access") if entry.get("access") else None
            # Should be a reference to an existing SnmpView
            #snmp_community_values_dict['view'] = entry.get("view") if entry.get("view") else None
            snmp_community_values_dict['ipv4_acl'] = entry.get("ipv4_acl") if entry.get("ipv4_acl") else None
            snmp_community_values_dict['ipv6_acl'] = entry.get("ipv6_acl") if entry.get("ipv6_acl") else None
            if entry.get("source_interface"):
                for intf_name, intf in self.parsed_config.interfaces.items():
                    intf_type = intf.get('type') if isinstance(intf, dict) else getattr(intf, 'type', None)
                    intf_vlan_id = intf['vlan_id'].get('value') if isinstance(intf, dict) and intf.get('vlan_id') else getattr(intf, 'vlan_id', None)
                    if intf_type == 'l3ipvlan' and intf_vlan_id == int(entry.get("source_interface").replace('Vlan','')):
                        intf_ref = ReferenceTo(pointer=f"interfaces.{intf_name}")
                        break
                snmp_community_values_dict['source_interface'] = intf_ref

            snmp_communities_dict[f'community_{i}'] = self.removekey(SnmpCommunity(**snmp_community_values_dict), 'metadata')
        self.parsed_config.system.snmp.communities = snmp_communities_dict

    def parse_snmp(self) -> None:
        """Parse SNMP configuration."""
        command = "show running snmp"

        parsed_data = parse_output(
            platform=self.platform,
            template_dir=self.custom_templates_dir,
            command=command,
            data=self.running_config
            #data=self.load_running_config("/Users/jani/scripts/acex/docs/examples/test_run/sample_running.txt") # Using this for testing with a static config file, replace with self.running_config for actual use
        )

        # SNMP parsing logic would go here, similar to NTP and SSH parsing
        snmp_config_values_dict = {}

        for entry in parsed_data:
            if entry.get('host'):
                snmp_config_values_dict['enabled'] = True
            snmp_config_values_dict['location'] = entry.get("location") if entry.get("location") else None
            snmp_config_values_dict['contact'] = entry.get("contact") if entry.get("contact") else None
            snmp_config_values_dict['engine_id'] = entry.get("engine_id") if entry.get("engine_id") else None

            snmp_config = self.removekey(SnmpConfig(**snmp_config_values_dict), 'metadata')

        self.parsed_config.system.snmp.config = snmp_config