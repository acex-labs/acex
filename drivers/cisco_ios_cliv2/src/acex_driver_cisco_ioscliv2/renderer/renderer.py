from typing import Any

from acex_devkit.configdiffer import Diff
from acex_devkit.drivers import RendererBase
from acex_devkit.models.composed_configuration import ComposedConfiguration


class CiscoIOSCLIRenderer(RendererBase):
    # Render config patches from diff below, move to better place laterz
    def render_patch(self, diff: Diff, node_instance: Any): ...
    def render(self, configuration: ComposedConfiguration, asset) -> Any: ...
