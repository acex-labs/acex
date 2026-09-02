"""Cisco IOS CLI dialect: block-indented syntax, and the attribute maps for interfaces.

Spike scope only — see /Users/johan/.claude/plans/validated-finding-petal.md. Covers
`EthernetCsmacdInterface.name/description/enabled` to prove that one DialectAttributeMap per
attribute drives both `Mapper.render` and `Mapper.parse`, instead of the separate Jinja2
(render) / TextFSM (parse) code paths used elsewhere in this repo today.
"""

from acex_devkit.drivers.mapper import Dialect, DialectAttributeMap, DialectMultilineMap, ParseFrame
from acex_devkit.models.composed_configuration import EthernetCsmacdInterface, SystemConfig


class CiscoDialect(Dialect):
    """Cisco IOS block syntax: a header line (`interface X`) followed by lines indented with a
    single leading space, with no explicit closing token — the next line back at column 0
    (or a bare `!`) ends the block."""

    component_order = (SystemConfig, EthernetCsmacdInterface)
    # Only keyed-collection types need an entry — SystemConfig is a singleton (no identity,
    # applied directly). Where each type lives in the tree and whether it's a dict or a
    # singleton is derived automatically from ComposedConfiguration's own schema (see
    # acex_devkit.drivers.mapper.COMPONENT_PATHS), not declared here.
    identity_maps = {EthernetCsmacdInterface: "name"}
    attribute_order = {
        SystemConfig: ("hostname", "domain_name", "motd_banner"),
        EthernetCsmacdInterface: ("name", "description", "enabled"),
    }
    indent_unit = " "

    def component_separator(self) -> str | None:
        return "!"

    def resolve_frame(self, line: str, stack: list[ParseFrame]) -> int:
        indent = len(line) - len(line.lstrip(self.indent_unit))
        count = 0
        for frame in reversed(stack[1:]):  # never pop the root sentinel
            if frame.depth >= indent:
                count += 1
            else:
                break
        return count


INTERFACE_MAPS = [
    DialectAttributeMap(EthernetCsmacdInterface, "name", "interface {name}"),
    DialectAttributeMap(EthernetCsmacdInterface, "description", "description {description}"),
    DialectAttributeMap(EthernetCsmacdInterface, "enabled", "no shutdown", value=True),
    DialectAttributeMap(EthernetCsmacdInterface, "enabled", "shutdown", value=False),
]

SYSTEM_MAPS = [
    DialectAttributeMap(SystemConfig, "hostname", "hostname {hostname}"),
    DialectAttributeMap(SystemConfig, "domain_name", "domain-name {domain_name}"),
    DialectMultilineMap(SystemConfig, "motd_banner", "banner motd {delim}", default_delimiter="^C"),
]
