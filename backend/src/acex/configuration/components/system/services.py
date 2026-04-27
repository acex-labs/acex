from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import Services as ServicesAttributes

class Services(ConfigComponent):
    type = "services"
    model_cls = ServicesAttributes