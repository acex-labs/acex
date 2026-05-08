from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import ClockConfig as ClockAttributes


class Clock(ConfigComponent):
    type = "clock"
    model_cls = ClockAttributes