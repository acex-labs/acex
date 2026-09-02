from typing import Any

from acex_devkit.drivers import RendererBase
from acex_devkit.drivers.mapper import Mapper
from acex_devkit.models.composed_configuration import ComposedConfiguration

from acex_driver_cisco_ioscliv2.dialect import INTERFACE_MAPS, SYSTEM_MAPS, CiscoDialect


class CiscoIOSCLIRenderer(RendererBase):
    # render_patch not implemented yet for this spike — RendererBase.render_patch's
    # NotImplementedError default applies until it is.

    def __init__(self):
        # Spike: interfaces only, via the DialectAttributeMap/Mapper concept. See
        # /Users/johan/.claude/plans/validated-finding-petal.md — everything else in
        # ComposedConfiguration is out of scope until the concept's proven.
        #
        # Exposed as `self.mapper` (not a local var) so `NetworkElementDriver.capabilities` can
        # read `mapper.supported_paths()` without the driver author declaring anything extra.
        self.mapper = Mapper(CiscoDialect(), [*INTERFACE_MAPS, *SYSTEM_MAPS])

    def render(self, configuration: ComposedConfiguration, asset) -> Any:
        return self.mapper.render(configuration).text
