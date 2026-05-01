from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from acex.plugins.neds.core import RendererBase
from acex_devkit.configdiffer import Diff
from acex_devkit.configdiffer.command import Command, Context
from acex_devkit.models.composed_configuration import ComposedConfiguration

from .augment_renderers import resolve_augment_lines


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


# Junos uses different interface name prefixes per port speed.
# Speeds are in kbps to match the AttributeValue[int] convention used elsewhere.
PORT_PREFIX_BY_SPEED = {
    1_000_000: "ge",         # 1 Gbps
    10_000_000: "xe",        # 10 Gbps
    25_000_000: "et",        # 25 Gbps (some platforms)
    40_000_000: "et",        # 40 Gbps
    100_000_000: "et",       # 100 Gbps
}


class JunosCLIRenderer(RendererBase):

    def _load_template_file(self) -> str:
        path = Path(__file__).parent
        env = Environment(loader=FileSystemLoader(path), undefined=StrictUndefined)
        return env.get_template("template.j2")

    def render(self, configuration: ComposedConfiguration, asset) -> Any:
        """Render the configuration model for Junos CLI devices."""
        if isinstance(configuration, ComposedConfiguration):
            configuration = configuration.model_dump(mode="json")
        else:
            raise ValueError(
                f"Configuration must be a ComposedConfiguration instance. Not {type(configuration)}"
            )

        processed_config = self.pre_process(configuration, asset)
        template = self._load_template_file()
        return template.render(configuration=processed_config)

    # ── Patch rendering ─────────────────────────────────────────
    # Junos `set` / `delete` lines are fully qualified per command, so
    # there's no enter/exit context to track — generators emit complete
    # lines and rendering is just a join.

    def _register(self):
        self.registry.register(('system', 'config'), self._generate_system_config_commands)
        self.registry.register(('interfaces', '*'), self._generate_interface_config_commands)

    def render_patch(self, diff: Diff, node_instance: "NodeInstance"):
        """Render device commands for a Diff using registered generators."""
        self.registry = GeneratorRegistry()
        self._register()

        commands: List[Command] = []
        for change in diff.get_all_changes():
            generator = self.registry.resolve(tuple(change.path))
            if generator is None:
                continue
            commands.extend(generator(change, node_instance))

        return "\n".join(c.command for c in commands)

    def _generate_system_config_commands(self, component_change, node_instance) -> List[Command]:
        ctx = Context(path=[])
        commands: List[Command] = []
        for attr in component_change.changed_attributes:
            if attr.attribute_name == "hostname":
                if component_change.op in ("add", "change"):
                    commands.append(Command(context=ctx, command=f"set system host-name {attr.after.value}"))
                elif component_change.op == "remove":
                    commands.append(Command(context=ctx, command="delete system host-name"))
        return commands

    def _generate_interface_config_commands(self, component_change, node_instance) -> List[Command]:
        # Stub mirroring the Cisco renderer's placeholder — real attribute
        # mapping per change.op / attr.attribute_name lands here.
        ctx = Context(path=component_change.path)
        return [Command(context=ctx, command="set interfaces TODO description \"TODO\"")]

    def pre_process(self, configuration: dict, asset) -> Dict[str, Any]:
        """Pre-process the configuration model before rendering j2."""
        configuration = self._physical_interface_names(configuration, asset)
        self._resolve_lag_lacp(configuration)
        configuration["augment_lines"] = resolve_augment_lines(configuration)
        return configuration

    def _resolve_lag_lacp(self, config: dict) -> None:
        """
        Bubble per-member LACP settings up to the LAG itself, plus count LAGs
        for chassis-level `aggregated-devices` config. The model keeps LACP
        timing/mode on member ports (Cisco-flavored convention); Junos needs
        them on the LAG.

        Sets on each LAG: `_lacp_enabled`, `_lacp_mode`, `_lacp_interval`.
        Sets on config root: `_lag_count`.
        """
        interfaces = config.get("interfaces") or {}

        members_by_lag: Dict[int, list] = defaultdict(list)
        for intf in interfaces.values():
            if intf.get("type") != "ethernetCsmacd":
                continue
            agg = (intf.get("aggregate_id") or {}).get("value")
            if agg is None:
                continue
            members_by_lag[agg].append(intf)

        for intf in interfaces.values():
            if intf.get("type") != "ieee8023adLag":
                continue
            intf["_lacp_enabled"] = False
            intf["_lacp_interval"] = None
            agg_id = (intf.get("aggregate_id") or {}).get("value")
            if agg_id is None:
                continue
            for member in members_by_lag.get(agg_id, []):
                if (member.get("lacp_enabled") or {}).get("value"):
                    intf["_lacp_enabled"] = True
                    mode = (member.get("lacp_mode") or {}).get("value")
                    intf["_lacp_mode"] = mode if mode in ("active", "passive") else "active"
                    interval = (member.get("lacp_interval") or {}).get("value")
                    if interval:
                        intf["_lacp_interval"] = interval
                    break

        config["_lag_count"] = sum(1 for i in interfaces.values() if i.get("type") == "ieee8023adLag")

    def _physical_interface_names(self, config: dict, asset) -> dict:
        """
        Resolve physical/management interface names per Junos conventions.

        - ethernetCsmacd: ge-/xe-/et- prefix per speed, suffix `<stack>/<module>/<port>`
          using the asset's stack_index/module_index/index from the model.
        - managementInterface: hardcoded to `me0` (switch-style); routers use
          `fxp0` — extend if/when we model that.
        - softwareLoopback: `lo0` with the index becoming the unit number, set
          on the model so the template can use it.
        """
        for _, intf in (config.get("interfaces") or {}).items():
            t = intf.get("type")

            if t == "ethernetCsmacd":
                speed = (intf.get("speed") or {}).get("value") or 1_000_000
                prefix = PORT_PREFIX_BY_SPEED.get(speed, "ge")
                stack_index = (intf.get("stack_index") or {}).get("value") or 0
                module_index = (intf.get("module_index") or {}).get("value") or 0
                port_index = intf["index"]["value"]
                intf["name"] = f"{prefix}-{stack_index}/{module_index}/{port_index}"

            elif t == "managementInterface":
                # Junos out-of-band mgmt; default to me0 for switches.
                intf["name"] = "me0"

            elif t == "softwareLoopback":
                # Junos models loopback as lo0 unit N — name doesn't appear
                # standalone, but having it deterministic helps templates.
                intf["name"] = "lo0"

            elif t == "ieee8023adLag":
                # Junos uses ae<N> for aggregated Ethernet.
                intf["name"] = f"ae{intf['index']['value']}"

        return config
