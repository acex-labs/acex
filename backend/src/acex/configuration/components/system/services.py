from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import (
    Services as ServicesAttributes,
    ServicesConfig as ServicesConfigAttributes
)

class Services(ConfigComponent):
    type = "services"
    model_cls = ServicesAttributes
    
class ServicesConfig(ConfigComponent):
    type = "services_config"
    model_cls = ServicesConfigAttributes