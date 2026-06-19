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

from .device_types.resolver import get_model


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

    @property
    def _model_directory(self) -> str:
        """Return the directory path for Cisco models."""
        package_dir = os.path.dirname(__file__)
        return os.path.join(package_dir, "device_types/models")

    def _load_template_file(self, asset) -> str:
        """Load a Jinja2 template file."""
        # handle cluster and single assets.
        template_name = "template.j2"

        path = Path(__file__).parent
        env = Environment(
            loader=FileSystemLoader(path), undefined=StrictUndefined
        )  # StrictUndefined to catch undefined variables, testing

        env.filters["cidr_to_addrmask"] = cidr_to_addrmask
        template = env.get_template(template_name)
        return template

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

    def _add_vrf_to_intefaces(self, config):
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
                    ref_path = interface["pointer"]
                    if isinstance(ref_path, str) and ref_path:
                        intf = config["interfaces"][ref_path.split(".")[1]]
                        intf["vrf"] = vrf["name"]["value"]

    def pre_process(self, configuration, asset) -> Dict[str, Any]:
        """Pre-process the configuration model before rendering j2."""

        # Render physical interface config
        self._add_vrf_to_intefaces(configuration)
        self._render_frontpanel_ports(configuration, asset)
        self._ssh_interface(configuration)
        self._logging_trap_severity(configuration)
        self._pre_process_vty_lines(configuration)
        # self.lacp_load_balancing(configuration)

        if hasattr(asset, "assets"):
            os_version = asset.assets[0].os_version
        else:
            os_version = asset.os_version

        configuration["asset"] = {"version": os_version}
        return configuration

    def _pre_process_vty_lines(self, config):
        """
        Group consecutive VTY lines with identical settings into ranges.
        Stores result in config['_vty_groups'] for template consumption.
        """
        logging_cfg = config.get("system", {}).get("logging", {})
        vty_container = logging_cfg.get("vty") or {}
        vty_lines = vty_container.get("lines") or {}

        if not vty_lines:
            config["_vty_groups"] = []
            return

        # Sort by line_number
        sorted_lines = sorted(
            vty_lines.values(), key=lambda v: v.get("line_number", {}).get("value", 0)
        )

        def _extract_settings(line):
            """Extract a comparable settings dict from a VTY line."""
            # ACL
            ipv4acl = line.get("ipv4acl")
            acl_name = (
                ipv4acl.get("pointer", "").split(".")[-1]
                if ipv4acl and ipv4acl.get("pointer")
                else None
            )
            acl_dir = (
                line.get("acl_direction", {}).get("value", "in")
                if line.get("acl_direction")
                else "in"
            )
            acl_ni = (
                line.get("acl_network_instance", {}).get("value")
                if line.get("acl_network_instance")
                else None
            )

            # Transport
            transport = (
                line.get("transport_input", {}).get("value", "ssh")
                if line.get("transport_input")
                else "ssh"
            )

            # Logging
            log_sync = (
                bool(line.get("logging_synchronous", {}).get("value"))
                if line.get("logging_synchronous")
                else False
            )

            # AAA from augments
            augments = line.get("augments") or {}
            login_auth = None
            authz_exec = None
            authz_commands = None
            for aug in augments.values():
                if aug.get("type") == "cisco_vty_aaa":
                    la = aug.get("login_authentication")
                    login_auth = (
                        la.get("pointer", "").split(".")[-1]
                        if la and la.get("pointer")
                        else la.get("value") if la else None
                    )
                    ae = aug.get("authorization_exec")
                    authz_exec = (
                        ae.get("pointer", "").split(".")[-1]
                        if ae and ae.get("pointer")
                        else ae.get("value") if ae else None
                    )
                    ac = aug.get("authorization_commands")
                    authz_commands = (
                        ac.get("pointer", "").split(".")[-1]
                        if ac and ac.get("pointer")
                        else ac.get("value") if ac else None
                    )
                    break

            return {
                "acl_name": acl_name,
                "acl_direction": acl_dir,
                "acl_network_instance": acl_ni,
                "transport_input": transport,
                "logging_synchronous": log_sync,
                "login_authentication": login_auth,
                "authorization_exec": authz_exec,
                "authorization_commands": authz_commands,
            }

        # Group consecutive lines with identical settings
        groups = []
        for line in sorted_lines:
            line_num = line.get("line_number", {}).get("value", 0)
            settings = _extract_settings(line)

            if (
                groups
                and groups[-1]["settings"] == settings
                and groups[-1]["end_line"] == line_num - 1
            ):
                groups[-1]["end_line"] = line_num
            else:
                groups.append(
                    {
                        "start_line": line_num,
                        "end_line": line_num,
                        "settings": settings,
                    }
                )

        # Flatten for template: merge settings into top level
        result = []
        for g in groups:
            entry = {"start_line": g["start_line"], "end_line": g["end_line"]}
            entry.update(g["settings"])
            result.append(entry)

        config["_vty_groups"] = result

    def _render_frontpanel_ports(self, configuration, asset):
        """
        Entry method for rendering frontpanel interfaces.
        If asset.type is cluster or single asset, this
        method resolves and loops accordingly.
        """
        if asset.type == "asset":
            model_data = get_model(asset.hardware_model, self._model_directory)
            port_slots = self._render_frontpanel_port_slots(
                0, configuration, model_data
            )
            configuration = self._update_frontpanel_ports(configuration, port_slots)
        elif asset.type == "asset_cluster":
            all_slots = []
            for stack_index, asset in enumerate(asset.assets):
                model_data = get_model(asset.hardware_model, self._model_directory)
                all_slots.extend(
                    self._render_frontpanel_port_slots(
                        stack_index, configuration, model_data
                    )
                )

            configuration = self._update_frontpanel_ports(configuration, all_slots)

    def _render_frontpanel_port_slots(self, stack_index, configuration, model_data):
        """
        Build a list of "interface slots". These slots are to be filled with config
        from configuration, such as speed, before passed to template rendering.
        """
        intf_slots = []

        interface_pattern = model_data["name_pattern"]
        prefix_map = model_data["prefix_map"]
        idx_start = model_data["interface_index_start"]
        midx_start = model_data["module_index_start"]
        sidx_start = model_data["stack_index_start"]

        for interface_slot in model_data["interfaces"]:

            # Get prefix based on configured speed
            speed = self._get_configured_speed(configuration, interface_slot)
            prefix = prefix_map.get(speed)

            # Compile full interface name
            ifname = self._compile_interface_name(
                prefix=prefix,
                stack_index=stack_index,
                interface_slot=interface_slot,
                model_data=model_data,
            )

            intf_slots.append(
                {
                    "name": ifname,
                    "index": interface_slot["index"],
                    "module_index": interface_slot["module_index"],
                    "stack_index": stack_index,
                }
            )

        return intf_slots

    def _update_frontpanel_ports(self, configuration, slots):
        """
        Fetch corresponding configuration for each frontpanel port slot.
        """
        interfaces_without_slots = []

        for k, v in configuration["interfaces"].items():
            if v["type"] == "ethernetCsmacd":
                idx = v["index"]["value"]
                midx = v["module_index"]["value"]
                sidx = v["stack_index"]["value"]
                slot = self._get_slot(idx, midx, sidx, slots)

                if slot is None:
                    interfaces_without_slots.append(k)
                else:
                    v["name"] = slot["name"]

        for interface in interfaces_without_slots:
            configuration["interfaces"].pop(interface)

        return configuration

    def _get_slot(self, index, module_index, stack_index, slots):
        """Extracts a slot definition or None"""
        for slot in slots:
            if (
                slot["index"] == index
                and slot["module_index"] == module_index
                and slot["stack_index"] == stack_index
            ):
                return slot
        return None

    def _compile_interface_name(
        self, *, prefix: str, stack_index: int, interface_slot: dict, model_data: dict
    ):
        """
        Compiles full interface name from device_types/models file
        """

        pattern = model_data["name_pattern"]
        idx_offset = model_data["interface_index_start"]
        midx_offset = model_data["module_index_start"]
        sidx_offset = model_data["stack_index_start"]

        name = pattern.format_map(
            {
                "prefix": prefix,
                "stack_index": stack_index + sidx_offset,
                "module_index": interface_slot["module_index"] + midx_offset,
                "index": interface_slot["index"] + idx_offset,
            }
        )

        return name

    def _get_configured_speed(self, configuration: dict, interface_slot: dict):
        """extract configured interface speed from config map"""

        for k, v in configuration["interfaces"].items():
            configured_speed = v.get("speed", {}).get("value", 1000000)

        return configured_speed
