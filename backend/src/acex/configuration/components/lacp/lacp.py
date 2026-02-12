from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import LacpConfig as LacpAttributes

class LacpConfig(ConfigComponent): 
    type = "lacp"
    model_cls = LacpAttributes
