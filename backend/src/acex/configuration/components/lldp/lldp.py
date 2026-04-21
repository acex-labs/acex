
from acex.configuration.components.base_component import ConfigComponent
from acex.configuration.components.interfaces import Interface

from acex_devkit.models.composed_configuration import (
    LldpConfigAttributes,
)

class LldpConfig(ConfigComponent): 
    type = "lldp_config"
    model_cls = LldpConfigAttributes