from acex_devkit.configdiffer import Diff
from acex_devkit.drivers import Codec
from acex_devkit.drivers.mapper import Mapper
from acex_devkit.models.codec_result import ParseResult, RenderResult
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.node_response import NodeInstance

from acex_driver_waystream_ibos.normalizer import IbosNormalizer
from acex_driver_waystream_ibos.syntax import BLOCKS


class IbosCodec(Codec[str]):
    mapper = Mapper(BLOCKS, indent=" ")
    normalizer = IbosNormalizer()

    def render(self, config: ComposedConfiguration, node: NodeInstance) -> RenderResult[str]:
        raise NotImplementedError("Exercise 8: render the configuration")

    def parse(self, raw: str, node: NodeInstance) -> ParseResult:
        raise NotImplementedError("Exercise 6: parse the running configuration")

    def render_patch(self, diff: Diff, node: NodeInstance) -> RenderResult[str]:
        raise NotImplementedError("Not part of the exercises: patches come after the first full render works")

    def normalize(self, raw: str) -> str:
        raise NotImplementedError("Exercise 4: normalize, with the normalizer")

    def mask(self, raw: str) -> str:
        raise NotImplementedError("Exercise 5: mask, with the normalizer")
