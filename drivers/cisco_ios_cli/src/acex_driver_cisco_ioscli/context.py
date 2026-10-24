from acex_devkit.drivers.mapper import Context
from acex_devkit.models.node_response import NodeInstance

from acex_driver_cisco_ioscli.naming import CiscoInterfaceNaming


class CiscoContext(Context):
    """The node's OS release, for syntax that changed between releases, and its hardware, for port names."""

    def __init__(self, node: NodeInstance | None):
        super().__init__(node)
        self.naming = CiscoInterfaceNaming(node)
