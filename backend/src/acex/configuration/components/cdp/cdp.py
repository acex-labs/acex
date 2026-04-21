
from acex.configuration.components.base_component import ConfigComponent

from acex_devkit.models.composed_configuration import (
    CdpConfigAttributes,
)

class CdpConfig(ConfigComponent): 
    type = "cdp_config"
    model_cls = CdpConfigAttributes