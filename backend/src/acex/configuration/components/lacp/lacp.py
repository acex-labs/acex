from acex.configuration.components.base_component import ConfigComponent
from acex.models.composed_configuration import LacpConfig as LacpAttributes

class LacpConfig(ConfigComponent): 
    type = "lacp"
    model_cls = LacpAttributes
