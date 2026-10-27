from acex_devkit.configdiffer import Diff
from acex_devkit.drivers import Codec
from acex_devkit.drivers.mapper import Mapper
from acex_devkit.models.codec_result import ParseResult, RenderResult
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.node_response import NodeInstance

from acex_driver_cisco_ioscli.context import CiscoContext
from acex_driver_cisco_ioscli.normalizer import CiscoIOSNormalizer
from acex_driver_cisco_ioscli.syntax import BLOCKS


class CiscoIOSCodec(Codec[str]):
    """Cisco IOS-XE CLI syntax. Render and parse share one Mapper, so the two directions cannot drift apart."""

    # IOS nests blocks one space deeper, with no closing token; `!` separates top-level components.
    mapper = Mapper(BLOCKS, indent=" ", separator="!")
    normalizer = CiscoIOSNormalizer()

    def render(self, config: ComposedConfiguration, node: NodeInstance) -> RenderResult[str]:
        return self.mapper.render(config, CiscoContext(node))

    def parse(self, raw: str, node: NodeInstance) -> ParseResult:
        return self.mapper.parse(self.normalize(raw), CiscoContext(node))

    def render_patch(self, diff: Diff, node: NodeInstance) -> str:
        raise NotImplementedError(f"{type(self).__name__} does not implement render_patch yet")

    def normalize(self, raw: str) -> str:
        return self.normalizer.normalize(raw).config

    def mask(self, raw: str) -> str:
        return self.normalizer.mask(raw).config
