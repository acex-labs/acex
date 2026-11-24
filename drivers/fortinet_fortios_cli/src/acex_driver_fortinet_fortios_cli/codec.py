from acex_devkit.configdiffer import Diff
from acex_devkit.drivers import Codec
from acex_devkit.drivers.mapper import Context, Mapper
from acex_devkit.models.codec_result import ParseResult, RenderMetadata, RenderResult, UnmatchedLine
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.node_response import NodeInstance

from acex_driver_fortinet_fortios_cli import framing
from acex_driver_fortinet_fortios_cli.normalizer import FortiOSNormalizer
from acex_driver_fortinet_fortios_cli.syntax import BLOCKS


class FortiOSCodec(Codec[str]):
    """FortiOS CLI syntax. Render and parse share one Mapper, so the two directions cannot drift apart.

    FortiOS nests by indentation like the mapper does, but four spaces a level where the mapper takes a one
    character indent, and it closes every `config` with `end` and every `edit` with `next`, which the mapper knows
    nothing of. `render` reframes what the mapper wrote and `parse` what it is about to read (see `framing`),
    moving the spans of both so they still point at the right lines.

    A patch is not rendered yet. The mapper removes a component by negating its line with `no`, where FortiOS
    uses `delete` and `unset`, so every change is reported as unrendered."""

    mapper = Mapper(BLOCKS, indent=" ")
    normalizer = FortiOSNormalizer()

    def render(self, config: ComposedConfiguration, node: NodeInstance) -> RenderResult[str]:
        rendered = self.mapper.render(config, Context(node))
        layout = framing.insert(rendered.payload)
        spans = [layout.span(span) for span in rendered.metadata.spans]
        return RenderResult(payload=layout.text, metadata=rendered.metadata.model_copy(update={"spans": spans}))

    def parse(self, raw: str, node: NodeInstance) -> ParseResult:
        layout = framing.remove(self.normalize(raw))
        parsed = self.mapper.parse(layout.text, Context(node))
        spans = [layout.span(span) for span in parsed.metadata.spans]
        unmatched = [
            UnmatchedLine(line=framing.widen(entry.line), parents=[framing.widen(parent) for parent in entry.parents])
            for entry in parsed.metadata.unmatched
        ]
        metadata = parsed.metadata.model_copy(update={"spans": spans, "unmatched": unmatched})
        return parsed.model_copy(update={"metadata": metadata})

    def render_patch(self, diff: Diff, node: NodeInstance) -> RenderResult[str]:
        return RenderResult(
            payload="",
            metadata=RenderMetadata(unrendered=[change.path for change in diff.get_all_changes()]),
        )

    def normalize(self, raw: str) -> str:
        return self.normalizer.normalize(raw).config

    def mask(self, raw: str) -> str:
        return self.normalizer.mask(raw).config
