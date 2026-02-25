from typing import Any, Dict, Optional, Callable, List
from acex_devkit.configdiffer import Diff
from acex_devkit.configdiffer.command import Command, Context
from acex.plugins.neds.core import RendererBase
from acex_devkit.models.composed_configuration import ComposedConfiguration
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from .filters import cidr_to_addrmask


class GeneratorRegistry:
    def __init__(self):
        self._patterns: list[tuple[tuple, Callable]] = []

    def register(self, pattern: tuple, generator: Callable):
        self._patterns.append((pattern, generator))

    def resolve(self, path: tuple):
        for pattern, generator in self._patterns:
            if self._match(path, pattern):
                return generator
        return None

    def _match(self, path, pattern):
        if len(path) < len(pattern):
            return False

        for p, pat in zip(path, pattern):
            if pat != "*" and p != pat:
                return False
        return True


class CiscoIOSCLIRenderer(RendererBase):

    def _load_template_file(self, asset) -> str:
        """Load a Jinja2 template file."""
        if asset.hardware_model == "vios_l2":
            template_name = "template_virtual.j2"
        else:
            template_name = "template.j2"
        path = Path(__file__).parent
        env = Environment(loader=FileSystemLoader(path),undefined=StrictUndefined) # StrictUndefined to catch undefined variables, testing
        #env = Environment(loader=FileSystemLoader(path), trim_blocks=True, lstrip_blocks=True) # För att slippa ha "-" i "{%-"
        env.filters["cidr_to_addrmask"] = cidr_to_addrmask
        template = env.get_template(template_name)
        return template


    def _register(self):
        """
        Registers patterns/generators to registry.

        for specific command generators, register them each and 
        map them to a pattern in the generator-registry
        """
        self.registry.register(('system', 'config'), self._generate_system_config_commands)
        self.registry.register(('interfaces', '*'), self._generate_interface_config_commands)

    def flatten(self, commands):
        output = []
        current_ctx = ()

        for cmd in commands:
            target_ctx = cmd.context.path

            # Om vi byter context
            if target_ctx != current_ctx:

                # Gå upp tills common prefix
                while not target_ctx[:len(current_ctx)] == current_ctx:
                    output.append("exit")
                    current_ctx = current_ctx[:-1]

                # Gå ner i nytt context
                for part in target_ctx[len(current_ctx):]:
                    output.append(part)
                    current_ctx += (part,)

            output.append(f" {cmd.command}")

        # Stäng alla contexts
        while current_ctx:
            output.append("exit")
            current_ctx = current_ctx[:-1]

        return output


    # Render config patches from diff below, move to better place laterz
    def render_patch(self, diff: Diff, node_instance: "NodeInstance"): 
        """
        Render specific commands for patching based on a diff.
        """
        # Create GeneratorRegistry and register patterns
        self.registry = GeneratorRegistry()
        self._register()

        commands = []
        for change in diff.get_all_changes():
            generator = self.registry.resolve(tuple(change.path))
            if generator is None:
                continue
            cmds = generator(change, node_instance)
            commands.extend(cmds)

        # TODO: Ordering

        # TODO: render context

        flat_commands = self.flatten(commands)
        cli_text = "!\r\n"
        for line in flat_commands:
            cli_text += line+"\r\n"
        cli_text += "!"
        return cli_text


    def render(self, configuration: ComposedConfiguration, asset) -> Any:
        """Render the configuration model for Cisco IOS CLI devices."""

        if isinstance(configuration, ComposedConfiguration):
            configuration = configuration.model_dump(mode="json")
        else:
            raise ValueError(f"Configuration must be a ComposedConfiguration instance. Not {type(configuration)}")
        # Ensure configuration is a plain dict (Pydantic model -> dict)
        #configuration = configuration.model_dump(mode="json")

        # Give the NED a chance to pre-process the config before rendering
        processed_config = self.pre_process(configuration, asset)
        template = self._load_template_file(asset)
        return template.render(configuration=processed_config)


    def _generate_system_config_commands(self, component_change, node_instance) -> List[Command]:
        """
        Generate config related to system config.
        """
        ctx = Context(path=[]) # tom eftersom dessa körs i rootnivå
        commands = []

        for attr in component_change.changed_attributes:
            if attr.attribute_name == "hostname":
                if component_change.op in ("add", "change"):
                    cmd_txt = f"hostname {attr.after.value}"
                elif component_change.op == "remove":
                    cmd_txt = "no hostname"

                commands.append(Command(context=ctx, command=cmd_txt))
        return commands


    def _generate_interface_config_commands(self, component_change, node_instance) -> List[Command]:
        """
        Generate config related to interface config.
        """
        ctx = Context(path=component_change.path)
        commands = []
        cmd = Command(context=ctx, command="desc hyvvää hirvi")

        commands.append(cmd)
        return commands











    def pre_process(self, configuration, asset) -> Dict[str, Any]:
        """Pre-process the configuration model before rendering j2."""
        configuration = self.physical_interface_names(configuration, asset)
        self.add_vrf_to_intefaces(configuration)
        self.ssh_interface(configuration)
        #self.lacp_load_balancing(configuration)
        configuration['asset'] = {
            'version': asset.os_version,
        }
        return configuration


    def ssh_interface(self, configuration):
        """Process SSH interface configurations if needed."""
        ssh = configuration.get('system', {}).get('ssh')
        if not ssh:
            return

        # Resolve the referenced interface name from ref_path
        # Add checks for path as it might be that it has not been set
        ssh_config = ssh.get('config') or {}
        ref = ssh_config.get('source_interface')
        if ref is not None:
            ref_path = ref.get('pointer')
            if isinstance(ref_path, str) and ref_path:
            #if not ref_path:
            #    return

                ref_name = ref_path.split('.')[1]
                intf = configuration.get('interfaces', {}).get(ref_name)
                if not intf:
                    return

                vlan_id = intf.get('vlan_id')
                if vlan_id is None:
                    return

                ssh_interface = f"Vlan{vlan_id}"
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
                    #ref_path = interface["metadata"]["ref_path"]
                    metadata = interface.get("metadata") or {}
                    ref_path = metadata.get("ref_path")
                    if isinstance(ref_path, str) and ref_path:
                        intf = config["interfaces"][ref_path.split('.')[1]]
                        intf["vrf"] = vrf["name"]["value"]

    def physical_interface_names(self, configuration, asset) -> None:
        """Assign physical interface names based on asset data."""

        for _,intf in configuration.get("interfaces", {}).items():
            if intf["metadata"]["type"] == "ethernetCsmacd":
                index = intf["index"]["value"]
                stack_index = (intf.get("stack_index") or {}).get("value")
                module_index = (intf.get("module_index") or {}).get("value")
                speed = (intf.get("speed") or {}).get("value") or 1000000 # Default to gig
                intf_prefix = self.get_port_prefix(asset.os, speed)
                intf_suffix = self.get_port_suffix(asset.hardware_model, index, stack_index, module_index)
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
                10000000: "TenGigabitEthernet",

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


    def get_port_suffix(self, hardware_model:str, index:int, stack_index:int=None, module_index:int=None) -> Optional[str]:
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
                if module_index is not None:
                    suffix_string = f"{stack_index}/{module_index}/{index+1}"
            else:
                if module_index is not None:
                    suffix_string = f"{module_index}/{index}"
                else:
                    suffix_string = f"0/{index}"
        elif index > max_index:
            if stack_index is not None:
                suffix_string = f"{stack_index}/1/{index - max_index + 1}"
                if module_index is not None:
                    suffix_string = f"{stack_index}/{module_index}/{index+1}"
            else:
                if module_index is not None:
                    suffix_string = f"{module_index}/{index}"
                else:
                    suffix_string = f"0/{index - max_index + 1}"
        return suffix_string
    
    # Create functions to handle ref paths

    # Create functions to handle port channels
    # def get_port_channel_suffix(self, hardware_model:str, index:int) -> Optional[str]:
