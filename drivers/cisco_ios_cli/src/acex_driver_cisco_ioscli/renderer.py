from logging import config
import os
from typing import Any, Dict, Optional, Callable, List
from acex_devkit.configdiffer import Diff
from acex_devkit.configdiffer.command import Command, Context
from acex.plugins.neds.core import RendererBase
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.logging import LoggingSeverity
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from .filters import cidr_to_addrmask
from .hardware_models import match_hardware_model

from .device_types.resolver import parse_model


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
        # handle cluster and single assets.
        if hasattr(asset, "assets"):
            first_asset = asset.assets[0]
        else:
            first_asset = asset

        if first_asset.hardware_model == "vios_l2":
            template_name = "template_virtual.j2"
        else:
            template_name = "template.j2"

        path = Path(__file__).parent
        env = Environment(
            loader=FileSystemLoader(path), undefined=StrictUndefined
        )  # StrictUndefined to catch undefined variables, testing
        # env = Environment(loader=FileSystemLoader(path), trim_blocks=True, lstrip_blocks=True) # För att slippa ha "-" i "{%-"
        env.filters["cidr_to_addrmask"] = cidr_to_addrmask
        template = env.get_template(template_name)
        return template

    def _model_directory(self) -> str:
        """Return the directory path for Cisco models."""
        package_dir = os.path.dirname(__file__)
        return os.path.join(package_dir, "device_types/models")

    def _register(self):
        """
        Registers patterns/generators to registry.

        for specific command generators, register them each and
        map them to a pattern in the generator-registry
        """
        self.registry.register(
            ("system", "config"), self._generate_system_config_commands
        )
        self.registry.register(
            ("interfaces", "*"), self._generate_interface_config_commands
        )

    def flatten(self, commands):
        output = []
        current_ctx = ()

        for cmd in commands:
            target_ctx = cmd.context.path

            # Om vi byter context
            if target_ctx != current_ctx:

                # Gå upp tills common prefix
                while not target_ctx[: len(current_ctx)] == current_ctx:
                    output.append("exit")
                    current_ctx = current_ctx[:-1]

                # Gå ner i nytt context
                for part in target_ctx[len(current_ctx) :]:
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
            cli_text += line + "\r\n"
        cli_text += "!"
        return cli_text

    def render(self, configuration: ComposedConfiguration, asset) -> Any:
        """Render the configuration model for Cisco IOS CLI devices."""

        """ TODO:
        - Interface preprocess
        - os och os version? ta från första noden? 

        """

        if isinstance(configuration, ComposedConfiguration):
            configuration = configuration.model_dump(mode="json")
        else:
            raise ValueError(
                f"Configuration must be a ComposedConfiguration instance. Not {type(configuration)}"
            )

        # Give the NED a chance to pre-process the config before rendering
        processed_config = self.pre_process(configuration, asset)

        # Render template and return payload
        template = self._load_template_file(asset)
        return template.render(configuration=processed_config)

    def _generate_system_config_commands(
        self, component_change, node_instance
    ) -> List[Command]:
        """
        Generate config related to system config.
        """
        ctx = Context(path=[])  # tom eftersom dessa körs i rootnivå
        commands = []

        for attr in component_change.changed_attributes:
            if attr.attribute_name == "hostname":
                if component_change.op in ("add", "change"):
                    cmd_txt = f"hostname {attr.after.value}"
                elif component_change.op == "remove":
                    cmd_txt = "no hostname"

                commands.append(Command(context=ctx, command=cmd_txt))
        return commands

    def _generate_interface_config_commands(
        self, component_change, node_instance
    ) -> List[Command]:
        """
        Generate config related to interface config.
        """
        ctx = Context(path=component_change.path)
        commands = []
        cmd = Command(context=ctx, command="desc hyvvää hirvi")

        commands.append(cmd)
        return commands

    def _ssh_interface(self, config):
        # ip ssh source-interface {'pointer': 'interfaces.vlan123_svi', 'metadata': {'type': 'str', 'value_source': 'reference'}}
        ssh_config = config.get("system", {}).get("ssh")
        ssh_raw_interface = (
            ssh_config.get("config", {}).get("source_interface") if ssh_config else None
        )
        if ssh_raw_interface and isinstance(ssh_raw_interface, dict):
            ref_path = ssh_raw_interface.get("pointer")
            if ref_path:
                ref_name = ref_path.split(".")[1]
                intf = config.get("interfaces", {}).get(ref_name)
                if intf:
                    vlan_id = intf.get("vlan_id")
                    if vlan_id is not None:
                        ssh_interface = f"Vlan{vlan_id.get('value')}"
                        # replace current source interface with formatted one for template use
                        ssh_config["config"]["source_interface"] = ssh_interface

        return config

    def _logging_trap_severity(self, config):
        logging_trap = (
            config.get("system", {})
            .get("logging", {})
            .get("config", {})
            .get("augments")
            or {}
        ).get("cisco.trap_logging")
        if logging_trap and logging_trap.get("severity"):
            # Translate severity to Cisco IOS format
            raw_severity = LoggingSeverity(logging_trap["severity"].get("value"))
            if "NOTICE" in raw_severity.value:
                logging_trap["severity"]["value"] = "informational"
            else:
                logging_trap["severity"]["value"] = raw_severity.value.lower()

        return config

    def pre_process(self, configuration, asset) -> Dict[str, Any]:
        """Pre-process the configuration model before rendering j2."""
        test_model = "test_model"
        # proper_model = asset.hardware_model
        if hasattr(asset, "assets"):
            for cl_asset in asset.assets:
                model_data = parse_model(
                    cl_asset.hardware_model, self._model_directory()
                )
                configuration = self.physical_interfaces(
                    configuration, model_data, cl_asset
                )
        else:
            model_data = parse_model(asset.hardware_model, self._model_directory())
            configuration = self.physical_interfaces(configuration, model_data, asset)
        # model_data = parse_model(
        #    test_model, self._model_directory()
        # )  # Testa att parsa modell, ta bort sen
        # configuration = self.physical_interfaces(configuration, model_data, asset)
        self._ssh_interface(configuration)
        self._logging_trap_severity(configuration)
        # self.add_vrf_to_intefaces(configuration)
        # self.ssh_interface(configuration)
        # self.lacp_load_balancing(configuration)

        if hasattr(asset, "assets"):
            os_version = asset.assets[0].os_version
        else:
            os_version = asset.os_version

        configuration["asset"] = {"version": os_version}
        return configuration

    #def _get_speed_value(self, raw_speed, default=1000000):
    #    if isinstance(raw_speed, dict):
    #        return raw_speed.get("value", default)
    #    if raw_speed is None:
    #        return default
    #    return raw_speed

    def _get_field_value(self, raw_value, default=None):
        if isinstance(raw_value, dict):
            return raw_value.get("value", default)
        if raw_value is None:
            return default
        return raw_value

    def physical_interfaces(self, configuration: dict, model_data: dict, asset):
        """
        Pre-process physical interfaces to have correct names based on model definition and config.
        """
        name_pattern = model_data.get(
            "name_pattern", "{prefix}{stack_index}/{module_index}/{index}"
        )
        stack_index_start = model_data.get("stack_index_start", 0)
        module_index_start = model_data.get("module_index_start", 0)
        interface_index_start = model_data.get("interface_index_start", 0)
        model_interfaces = model_data.get("interfaces", [])
        prefix_map = model_data.get("prefix_map") or {}
        used_model_interfaces = set()
        interfaces_without_slots = []

        for intf_name, intf in configuration.get("interfaces", {}).items():
            if intf.get("type") == "ethernetCsmacd":
                interface_stack_index = self._get_field_value(intf.get("stack_index"))
                asset_cluster_index = getattr(asset, "cluster_index", None)

                # If no asset cluster index, we skip below check.
                # If asset cluster index is true, but doesn't match the interface stack index, we continue as we otherwise
                # work on the wrong asset's interfaces.
                if (
                    asset_cluster_index is not None
                    and interface_stack_index is not None
                    and interface_stack_index != asset_cluster_index
                ):
                    continue

                # Cluster assets carry a stack index; standalone assets do not.
                # For standalone asset we use the stack_index_start value from the model
                sidx = interface_stack_index
                if sidx is None:
                    sidx = (
                        asset_cluster_index
                        if asset_cluster_index is not None
                        else stack_index_start
                    )
                midx = (
                    intf.get("module_index", {}).get("value") or 0
                    if intf.get("module_index") is not None
                    else 0
                )
                idx = intf.get("index", {}).get("value")
                speed = self._get_field_value(intf.get("speed"))

                prefix = self.get_prefix(intf, prefix_map)

                if prefix is None:
                    interfaces_without_slots.append(intf_name)
                    continue

                matched_model_interface = False

                for model_intf in model_interfaces:

                    if model_intf is None:
                        continue

                    model_interface_values = (
                        model_intf.get("module_index"),
                        model_intf.get("index"),
                    )

                    if sidx is not None:
                        model_interface_values = (sidx, *model_interface_values)

                    if model_interface_values in used_model_interfaces:
                        continue

                    if speed not in model_intf.get("speed_capabilities", []):
                        continue
                    idx = idx + interface_index_start if idx is not None else None
                    midx = midx + module_index_start if midx is not None else None
                    if idx == model_intf.get("index") and midx == model_intf.get(
                        "module_index"
                    ):
                        index_data = {
                            "module_index": midx,
                            "index": idx,
                        }
                        if sidx is not None:
                            sidx = sidx + stack_index_start
                            index_data["stack_index"] = sidx

                        intf["name"] = self.generate_inter_name(
                            index_data, name_pattern, prefix
                        )
                        used_model_interfaces.add(model_interface_values)
                        matched_model_interface = True
                        break

                if not matched_model_interface:
                    interfaces_without_slots.append(intf_name)

        for interface in interfaces_without_slots:
            configuration["interfaces"].pop(interface, None)

        return configuration

    def get_prefix(self, intf, prefix_map):
        for k, v in prefix_map.items():
            if k == self._get_field_value(intf.get("speed")):
                return v
        return None

    def generate_inter_name(self, index_data, name_pattern, prefix):
        if "stack_index" in index_data:
            name = name_pattern.format(
                prefix=prefix,
                stack_index=index_data.get("stack_index"),
                module_index=index_data.get("module_index"),
                index=index_data.get("index"),
            )
        else:
            name = name_pattern.format(
                prefix=prefix,
                module_index=index_data.get("module_index"),
                index=index_data.get("index"),
            )
        return name

    def ssh_interface(self, configuration):
        """Process SSH interface configurations if needed."""
        ssh = configuration.get("system", {}).get("ssh")
        if not ssh:
            return

        # Resolve the referenced interface name from ref_path
        # Add checks for path as it might be that it has not been set
        ssh_config = ssh.get("config") or {}
        ref = ssh_config.get("source_interface")
        if ref is not None:
            ref_path = ref.get("pointer")
            if isinstance(ref_path, str) and ref_path:
                # if not ref_path:
                #    return

                ref_name = ref_path.split(".")[1]
                intf = configuration.get("interfaces", {}).get(ref_name)
                if not intf:
                    return

                vlan_id = intf.get("vlan_id")
                if vlan_id is None:
                    return

                ssh_interface = f"Vlan{vlan_id}"
                # Store resolved interface for template use if needed
                ssh["config"]["source_interface"] = ssh_interface

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
                for _, interface in vrf["interfaces"].items():
                    # ref_path = interface["metadata"]["ref_path"]
                    metadata = interface.get("metadata") or {}
                    ref_path = metadata.get("ref_path")
                    if isinstance(ref_path, str) and ref_path:
                        intf = config["interfaces"][ref_path.split(".")[1]]
                        intf["vrf"] = vrf["name"]["value"]
