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
from copy import deepcopy

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

    def _interface_merge_key(self, old_key, intf):
        """
        Return a safe dictionary key for merging interfaces.
    
        Prefer generated intf["name"], but fall back to old_key if name is missing
        or is not a hashable/simple value.
    
        intf["name"] may sometimes be an ACEX-style dict:
            {"value": "...", "metadata": ...}
    
        So we use _get_field_value() before using it as a key.
        """
    
        name = self._get_field_value(intf.get("name"))
    
        if name is None:
            return old_key
    
        if isinstance(name, (str, int)):
            return str(name)
    
        # Defensive fallback for unexpected dict/list/etc.
        return old_key

    def pre_process(self, configuration, asset) -> Dict[str, Any]:
        """Pre-process the configuration model before rendering j2."""

        if hasattr(asset, "assets"):
            # change to logging output later, print for testing
            #print("Pre-processing clustered asset")

            original_interfaces = deepcopy(configuration.get("interfaces", {}))

            # Keep non-physical interfaces once.
            # Example: VLANs, Port-channels, loopbacks, SVIs, etc.
            merged_interfaces = {
                old_key: deepcopy(intf)
                for old_key, intf in original_interfaces.items()
                if intf.get("type") != "ethernetCsmacd"
            }

            for cl_asset in asset.assets:
                # change to logging output later, print for testing
                #print(f"Pre-processing asset in cluster {cl_asset}")

                model_data = parse_model(
                    cl_asset.hardware_model,
                    self._model_directory(),
                )

                # Work on a fresh copy for each stack member.
                per_asset_configuration = deepcopy(configuration)
                per_asset_configuration["interfaces"] = deepcopy(original_interfaces)

                per_asset_configuration = self._physical_interfaces(
                    per_asset_configuration,
                    model_data,
                    cl_asset,
                )

                # Merge only physical interfaces from this stack member.
                for old_key, intf in per_asset_configuration.get("interfaces", {}).items():
                    if intf.get("type") != "ethernetCsmacd":
                        continue

                    new_key = self._interface_merge_key(old_key, intf)
                    merged_interfaces[new_key] = intf

            configuration["interfaces"] = merged_interfaces

        else:
            # change to logging output later, print for testing
            #print(f"Pre-processing single asset {asset}")

            model_data = parse_model(
                asset.hardware_model,
                self._model_directory(),
            )

            configuration = self._physical_interfaces(
                configuration,
                model_data,
                asset,
            )




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

    # Work with both raw values and ACEX {"value": ...} format
    # if raw_value is a dict, we try to get "value" key, if it's not there we return default
    # if raw_value is not a dict and not None, we return it as is, if it's None we return default
    # default is set to None if not specified to a different value by the user
    def _get_field_value(self, raw_value, default=None):
        if isinstance(raw_value, dict):
            return raw_value.get("value", default)
        if raw_value is None:
            return default
        return raw_value

    def _get_internal_stack_index_for_asset(
        self,
        interface_stack_index,
        asset_cluster_index,
    ):
        """
        Decide whether the current interface belongs to the current asset.

        Rules:
        - configuration stack_index is always internal zero-based.
        - standalone assets are treated as internal stack 0.
        - stacked assets use asset.cluster_index: 0, 1, 2, ...

        Returns:
            int:
                Internal stack index to use.

            None:
                Interface does not belong to this asset.
        """

        # Standalone asset
        if asset_cluster_index is None:
            # If stack_index is missing, treat standalone as stack 0.
            if interface_stack_index is None:
                return 0

            # Standalone asset should only process internal stack 0.
            if interface_stack_index != 0:
                return None

            return 0

        # Stacked asset
        if interface_stack_index is not None and interface_stack_index != asset_cluster_index:
            return None

        return asset_cluster_index

    def _model_value_to_internal(self, value, start):
        """
        Convert a model/device-facing index into an internal zero-based index.

        Example:
            value=1, start=1 -> internal=0
            value=0, start=0 -> internal=0
        """
        if value is None:
            return None

        return value - start


    def _physical_interfaces(self, configuration: dict, model_data: dict, asset):
        """
        Pre-process physical interfaces to have correct names based on model definition and config.

        Important rules:
        - configuration stack_index/module_index/index always start at 0.
        - asset.cluster_index always starts at 0 for stacked assets.
        - model.yaml module_index/index may start at 0 or 1 depending on the Cisco model.
        - stack_index_start/module_index_start/interface_index_start are used to convert
          internal config values into rendered/model-facing values.
        """

        name_pattern = model_data.get(
            "name_pattern",
            "{prefix}{stack_index}/{module_index}/{index}",
        )

        stack_index_start = model_data.get("stack_index_start", 0)
        module_index_start = model_data.get("module_index_start", 0)
        interface_index_start = model_data.get("interface_index_start", 0)

        model_interfaces = model_data.get("interfaces", [])
        prefix_map = model_data.get("prefix_map") or {}

        used_model_interfaces = set()
        interfaces_without_slots = []

        for intf_name, intf in configuration.get("interfaces", {}).items():
            if intf.get("type") != "ethernetCsmacd":
                continue

            interface_stack_index = self._get_field_value(intf.get("stack_index"))
            asset_cluster_index = getattr(asset, "cluster_index", None)

            # Internal stack ownership check.
            # This is NOT rendered/model-facing.
            sidx = self._get_internal_stack_index_for_asset(
                interface_stack_index,
                asset_cluster_index,
            )

            if sidx is None:
                interfaces_without_slots.append(intf_name)
                continue

            # Configuration values are always internal zero-based.
            midx = self._get_field_value(intf.get("module_index"), default=0)
            idx = self._get_field_value(intf.get("index"))
            speed = self._get_field_value(intf.get("speed"), default=1000000)

            prefix = self._get_prefix(prefix_map, speed)

            if prefix is None:
                interfaces_without_slots.append(intf_name)
                continue

            matched_model_interface = False

            for model_intf in model_interfaces:

                if model_intf is None:
                    continue

                if speed not in model_intf.get("speed_capabilities", []):
                    continue

                # Convert internal config values to model/rendered-facing values.
                render_sidx = sidx + stack_index_start
                render_midx = (
                    midx + module_index_start
                    if midx is not None
                    else None
                )
                render_idx = (
                    idx + interface_index_start
                    if idx is not None
                    else None
                )

                # Duplicate tracking should use the same coordinate system as matching:
                # rendered/model-facing values.
                model_interface_values = (
                    render_sidx,
                    model_intf.get("module_index"),
                    model_intf.get("index"),
                )

                if model_interface_values in used_model_interfaces:
                    continue

                # model.yaml module_index/index are model/rendered-facing.
                # Therefore compare rendered config values to model values.
                if (
                    render_idx == model_intf.get("index")
                    and render_midx == model_intf.get("module_index")
                ):

                    index_data = {
                        "stack_index": render_sidx,
                        "module_index": render_midx,
                        "index": render_idx,
                    }

                    intf["name"] = self._generate_inter_name(
                        index_data,
                        name_pattern,
                        prefix,
                    )

                    used_model_interfaces.add(model_interface_values)
                    matched_model_interface = True
                    break

            if not matched_model_interface:
                interfaces_without_slots.append(intf_name)

        for interface in interfaces_without_slots:
            configuration["interfaces"].pop(interface, None)

        return configuration

    def _get_prefix(self,prefix_map, speed):
        for k, v in prefix_map.items():
            if k == speed:
                return v
        return None

    def _generate_inter_name(self, index_data, name_pattern, prefix):
        if "stack_index" in name_pattern:
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
