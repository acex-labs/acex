from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import SflowCollectorAttributes, SfloGlobalConfigAttributes

class SflowCollector(ConfigComponent): 
    type = "SflowCollector"
    model_cls = SflowCollectorAttributes

class SfloGlobalConfig(ConfigComponent):
    type = "SfloGlobalConfig"
    model_cls = SfloGlobalConfigAttributes