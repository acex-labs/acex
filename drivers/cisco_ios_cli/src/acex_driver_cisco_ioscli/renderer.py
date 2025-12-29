
from acex.plugins.neds.core import RendererBase
from typing import Any, Dict, Optional
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from .filters import cidr_to_addrmask


class CiscoIOSCLIRenderer(RendererBase):

    def _load_template_file(self) -> str:
        """Load a Jinja2 template file."""
        template_name = "template.j2"
        path = Path(__file__).parent
        env = Environment(loader=FileSystemLoader(path),undefined=StrictUndefined) # StrictUndefined to catch undefined variables, testing
        #env = Environment(loader=FileSystemLoader(path), trim_blocks=True, lstrip_blocks=True) # För att slippa ha "-" i "{%-"
        env.filters["cidr_to_addrmask"] = cidr_to_addrmask
        template = env.get_template(template_name)
        return template

    def render(self, logical_node: Dict[str, Any], asset) -> Any:
        """Render the configuration model for Cisco IOS CLI devices."""

        configuration = logical_node.configuration

        # Give the NED a chance to pre-process the config before rendering
        processed_config = self.pre_process(configuration, asset)
        template = self._load_template_file()
        return template.render(configuration=processed_config)

    def pre_process(self, configuration, asset) -> Dict[str, Any]:
        """Pre-process the configuration model before rendering j2."""
        configuration = self.physical_interface_names(configuration, asset)
        self.add_vrf_to_intefaces(configuration)
        self.ssh_interface(configuration)
        #self.lacp_load_balancing(configuration)
        return configuration

    #def handle_vty_lines(self, configuration):
    #    """Process VTY line configurations if needed."""
    #    vtys = configuration['vty']
    #    vty_lines = None
#
    #    if vtys is None:
    #        return
    #    for vty in vtys.values():
    #        vty_lines.append(vty['line_number']['value'])
    #    
    #    vtys['lines'] = vty_lines
    #    return configuration

    #def lacp_load_balancing(self, configuration):
    #    """Process LACP load balancing configurations if needed."""
    #    lacp = configuration.get('lacp')
    #    print('lacp: ', lacp)
    #    if not lacp:
    #        return
#
    #    load_balance_algorithm = lacp.get('config', {}).get('load_balance_algorithm')
    #    if not load_balance_algorithm:
    #        return
#
    #    print("load_balance_algorithm: ", load_balance_algorithm)
    #    # Regular handling for single algorithm
    #    if len(load_balance_algorithm) == 1:
    #        algorithm_str = load_balance_algorithm['value'][0]
    #        lacp['config']['load_balance_algorithm'] = algorithm_str+','
    #        return
#
    #    # Extended handling for Cisco IOS load balancing algorithms
    #    if len(load_balance_algorithm) >= 2:
    #    # Cisco IOS expects a comma-separated string of algorithms
    #    # Convert list to comma-separated string for template use
    #        algorithm_str = ','.join(load_balance_algorithm['value'])
    #        print("algorithm_str: ", algorithm_str)
    #        lacp['config']['load_balance_algorithm'] = algorithm_str
    #        return

    def ssh_interface(self, configuration):
        """Process SSH interface configurations if needed."""
        ssh = configuration.get('system', {}).get('ssh')
        if not ssh:
            return

        # Resolve the referenced interface name from ref_path
        ref = ssh.get('config', {}).get('source_interface', {})
        metadata = ref.get('metadata') or {}
        ref_path = metadata.get('ref_path')
        if not ref_path:
            return

        ref_name = ref_path.split('.')[1]
        intf = configuration.get('interfaces', {}).get(ref_name)
        if not intf:
            return

        vlan_id = intf.get('vlan_id')
        if vlan_id is None:
            return

        ssh_interface = f"vlan{vlan_id}"
        # Store resolved interface for template use if needed
        ssh['config']['source_interface'] = ssh_interface

    def add_vrf_to_intefaces(self, config):
        """
        Loops all network_instances and add vrf definition to 
        referenced interfaces
        """
        vrfs = config["network_instances"]
        for vrf_name, vrf in vrfs.items():
            if vrf["name"]["value"] == "global":
                ...
            else:
                for _,interface in vrf["interfaces"].items():
                    ref_path = interface["metadata"]["ref_path"]
                    intf = config["interfaces"][ref_path.split('.')[1]]
                    intf["vrf"] = vrf["name"]["value"]

    def physical_interface_names(self, configuration, asset) -> None:
        """Assign physical interface names based on asset data."""

        for _,intf in configuration.get("interfaces", {}).items():
            if intf["metadata"]["type"] == "ethernetCsmacd":
                index = intf["index"]["value"]
                stack_index = (intf.get("stack_index") or {}).get("value")
                speed = (intf.get("speed") or {}).get("value") or 1000000 # Default to gig
                intf_prefix = self.get_port_prefix(asset.os, speed)
                intf_suffix = self.get_port_suffix(asset.hardware_model, index, stack_index)
                intf["name"] = f"{intf_prefix}{intf_suffix}"
            if intf['metadata']['type'] == "ieee8023adLag":
                # Handle LAG interface names here
                index = intf["index"]["value"]
                intf["name"] = f"Port-channel{index}"
        return configuration

    def get_port_prefix(self, os:str, speed:int) -> Optional[str]:
        PREFIX_MAP = {
            "cisco_ios": {
                1000000: "GigabitEthernet",
            },
            "cisco_iosxe": {
                1000000: "GigabitEthernet",
                10000000: "TenGigabitEthernet",
                25000000: "TwentyFiveGigE",
                40000000: "FortyGigabitEthernet",
                100000000: "HundredGigE",
            },
            "cisco_iosxr": {
                1000000: "GigabitEthernet",
            },
            "cisco_nxos": {
                1000000: "Ethernet",
            },
        }
        return PREFIX_MAP.get(os, {}).get(speed) or "UnknownIfPrefix"


    def get_port_suffix(self, hardware_model:str, index:int, stack_index:int) -> Optional[str]:
        max_index = 0
        suffix_string = ""

        # TODO: Utöka med fler modeller
        match hardware_model:
            case "C9300-48":
                max_index = 48
            case "C9300-48P":
                max_index = 52
            case "C9500-48Y4C":
                max_index = 52

        # TODO: Fungerar upp till max port, förutsätter sen att man är 
        # på en modul, stöd för en modul eftersom vi inte vet maxportar på
        # tilläggsmodulen.
        if index <= max_index:
            if stack_index is not None:
                suffix_string = f"{stack_index}/0/{index+1}"
            else:
                suffix_string = f"1/0/{index+1}"
        elif index > max_index:
            if stack_index is not None:
                suffix_string = f"{stack_index}/1/{index - max_index + 1}"
            else:
                suffix_string = f"1/0/{index - max_index + 1}"
        return suffix_string
    
    # Create functions to handle ref paths

    # Create functions to handle port channels
    # def get_port_channel_suffix(self, hardware_model:str, index:int) -> Optional[str]:
