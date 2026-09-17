import ipaddress
from pathlib import Path
from typing import Any

from acex_devkit.configdiffer import Diff
from acex_devkit.configdiffer.command import Command, Context
from acex_devkit.drivers import RendererBase
from acex_devkit.models.composed_configuration import ComposedConfiguration
from jinja2 import Environment, FileSystemLoader, StrictUndefined


def _cidr_to_ipmask(cidr: str) -> str:
    """Convert '10.0.0.1/24' → '10.0.0.1 255.255.255.0' for FortiOS set ip."""
    try:
        iface = ipaddress.IPv4Interface(cidr)
        return f"{iface.ip} {iface.network.netmask}"
    except ValueError:
        return cidr


class GeneratorRegistry:
    def __init__(self):
        self._patterns: list[tuple[tuple, Any]] = []

    def register(self, pattern: tuple, generator):
        self._patterns.append((pattern, generator))

    def resolve(self, path: tuple):
        for pattern, generator in self._patterns:
            if self._match(path, pattern):
                return generator
        return None

    @staticmethod
    def _match(path, pattern):
        if len(path) < len(pattern):
            return False
        return all(pat == "*" or p == pat for p, pat in zip(path, pattern, strict=False))


class FortiOSCLIRenderer(RendererBase):
    def _load_template(self):
        env = Environment(
            loader=FileSystemLoader(Path(__file__).parent),
            undefined=StrictUndefined,
        )
        env.filters["ipmask"] = _cidr_to_ipmask
        return env.get_template("template.j2")

    def render(self, configuration: ComposedConfiguration, asset) -> str:
        if not isinstance(configuration, ComposedConfiguration):
            raise ValueError(f"Expected ComposedConfiguration, got {type(configuration)}")
        cfg = configuration.model_dump(mode="json")
        return self._load_template().render(configuration=cfg)

    def render_patch(self, diff: Diff, node_instance: Any) -> str:
        registry = GeneratorRegistry()
        registry.register(("system", "config"), self._generate_system_global_commands)
        registry.register(("interfaces", "*"), self._generate_interface_commands)

        commands: list[Command] = []
        for change in diff.get_all_changes():
            generator = registry.resolve(tuple(change.path))
            if generator is None:
                continue
            commands.extend(generator(change, node_instance))

        return "\n".join(c.command for c in commands)

    def _generate_system_global_commands(self, change, node_instance) -> list[Command]:
        ctx = Context(path=("system", "config"))
        out: list[Command] = []
        for attr in change.changed_attributes:
            if attr.attribute_name == "hostname":
                if change.op in ("add", "change"):
                    out += [
                        Command(context=ctx, command="config system global"),
                        Command(context=ctx, command=f"    set hostname {attr.after.value}"),
                        Command(context=ctx, command="end"),
                    ]
                elif change.op == "remove":
                    # FortiOS has no way to unset hostname; set to empty string.
                    out += [
                        Command(context=ctx, command="config system global"),
                        Command(context=ctx, command="    unset hostname"),
                        Command(context=ctx, command="end"),
                    ]
        return out

    def _generate_interface_commands(self, change, node_instance) -> list[Command]:
        ctx = Context(path=tuple(change.path))
        iface_name = change.path[-1] if change.path else "port1"
        out: list[Command] = []
        for attr in change.changed_attributes:
            if attr.attribute_name == "description":
                value = attr.after.value if change.op != "remove" else ""
                out += [
                    Command(context=ctx, command="config system interface"),
                    Command(context=ctx, command=f"    edit {iface_name}"),
                    Command(context=ctx, command=f'        set description "{value}"'),
                    Command(context=ctx, command="    next"),
                    Command(context=ctx, command="end"),
                ]
        return out
