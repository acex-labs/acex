from collections.abc import Iterator

from acex_devkit.configdiffer import Diff
from acex_devkit.drivers import Codec
from acex_devkit.drivers.mapper import Mapper
from acex_devkit.models.codec_result import ParseResult, RenderResult, Span
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.node_response import NodeInstance
from acex_devkit.models.spanning_tree import SpanningTreeGlobalAttributes

from acex_driver_cisco_ioscli.context import CiscoContext
from acex_driver_cisco_ioscli.normalizer import CiscoIOSNormalizer
from acex_driver_cisco_ioscli.syntax import BLOCKS

# `SpanningTreeGlobal.mode` is free text; these are the spellings that mean one of the three IOS modes.
SPANNING_TREE_MODES = {"pvst": "pvst", "rapid-pvst": "rapid-pvst", "mst": "mst", "mstp": "mst"}
# IOS itself starts in plain PVST, so a configuration that declares no mode asks for Rapid PVST+.
DEFAULT_SPANNING_TREE_MODE = "rapid-pvst"
# IOS nests blocks one space deeper, with no closing token; `!` separates top-level components.
SEPARATOR = "!"


class CiscoIOSCodec(Codec[str]):
    """Cisco IOS-XE CLI syntax. Render and parse share one Mapper, so the two directions cannot drift apart.

    The one exception is the spanning tree mode. `stp.config` has no shape the mapper can read and write back
    (the model types it as a collection, a configuration composed from components holds the one object), so
    that mode, and `extend system-id` which no model field covers, are written ahead of the rest in `render`
    and, like any line the syntax has no field for, are left unread by `parse`."""

    mapper = Mapper(BLOCKS, indent=" ", separator=SEPARATOR)
    normalizer = CiscoIOSNormalizer()

    def render(self, config: ComposedConfiguration, node: NodeInstance) -> RenderResult[str]:
        rendered = self.mapper.render(config, CiscoContext(node))
        return self.with_spanning_tree(rendered, *self.spanning_tree(config))

    def parse(self, raw: str, node: NodeInstance) -> ParseResult:
        return self.mapper.parse(self.normalize(raw), CiscoContext(node))

    def render_patch(self, diff: Diff, node: NodeInstance) -> RenderResult[str]:
        return self.mapper.render_patch(diff, CiscoContext(node))

    def normalize(self, raw: str) -> str:
        return self.normalizer.normalize(raw).config

    def mask(self, raw: str) -> str:
        return self.normalizer.mask(raw).config

    @staticmethod
    def declared_spanning_trees(
        config: ComposedConfiguration,
    ) -> Iterator[tuple[list[str], SpanningTreeGlobalAttributes]]:
        """Every `SpanningTreeGlobal` in the tree with its path. A configuration composed from components holds
        the object itself in `stp.config`, one read back from JSON a collection of them by name."""
        node = config.stp.config if config.stp else None
        if isinstance(node, dict):
            yield from ((["stp", "config", name], entry) for name, entry in node.items())
        elif node is not None:
            yield ["stp", "config"], node

    def spanning_tree(self, config: ComposedConfiguration) -> tuple[str, list[str] | None]:
        """The IOS mode a `SpanningTreeGlobal` declares and where that component sits in the tree, or the
        default mode and no path when none declares one."""
        for path, entry in self.declared_spanning_trees(config):
            mode = entry.mode.get_value() if entry.mode is not None else None
            keyword = SPANNING_TREE_MODES.get(str(mode).lower().replace("_", "-")) if mode else None
            if keyword:
                return keyword, path
        return DEFAULT_SPANNING_TREE_MODE, None

    def with_spanning_tree(self, rendered: RenderResult[str], mode: str, path: list[str] | None) -> RenderResult[str]:
        """`rendered` with the spanning tree lines first, and its spans moved down to where they ended up."""
        head = [f"spanning-tree mode {mode}", "spanning-tree extend system-id"]
        if rendered.payload:
            head.append(SEPARATOR)
        shift = len(head)
        spans = [
            Span(start=span.start + shift, end=span.end + shift, path=span.path) for span in rendered.metadata.spans
        ]
        if path is not None:
            spans.insert(0, Span(start=1, end=2, path=path))
        lines = [*head, rendered.payload] if rendered.payload else head
        return RenderResult(
            payload="\n".join(lines),
            metadata=rendered.metadata.model_copy(update={"spans": spans}),
        )
