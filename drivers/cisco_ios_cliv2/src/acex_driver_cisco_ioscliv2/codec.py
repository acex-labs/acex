from acex_devkit.configdiffer import Diff
from acex_devkit.drivers import Codec
from acex_devkit.drivers.mapper import Mapper
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.node_response import NodeInstance

from acex_driver_cisco_ioscliv2.dialect import INTERFACE_MAPS, SYSTEM_MAPS, CiscoDialect
from acex_driver_cisco_ioscliv2.normalizer.normalizer import CiscoIOSNormalizer


class CiscoIOSCodec(Codec[str]):
    """Cisco IOS-XE CLI syntax. Render and parse share one Mapper, so the two directions cannot drift apart."""

    mapper = Mapper(CiscoDialect(), [*INTERFACE_MAPS, *SYSTEM_MAPS])
    normalizer = CiscoIOSNormalizer()

    def render(self, config: ComposedConfiguration, node: NodeInstance) -> str:
        return self.mapper.render(config).text

    def parse(self, raw: str, node: NodeInstance) -> ComposedConfiguration:
        return self.mapper.parse(raw, root_factory=ComposedConfiguration).configuration

    def render_patch(self, diff: Diff, node: NodeInstance) -> str:
        raise NotImplementedError(f"{type(self).__name__} does not implement render_patch yet")

    def normalize(self, raw: str) -> str:
        return self.normalizer.normalize(raw).config

    def mask(self, raw: str) -> str:
        return self.normalizer.mask(raw).config
