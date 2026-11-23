from acex_devkit.drivers.mapper import Block, Line
from acex_devkit.models.composed_configuration import SystemConfig


class SystemGlobalSyntax(Block):
    path = "system.config"
    component = SystemConfig
    header = Line("config system global")
    single = True
    body = (Line('set hostname "{hostname}"'),)


BLOCKS = [
    SystemGlobalSyntax(),
]
