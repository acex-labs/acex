from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import VTPAttributes

class VTP(ConfigComponent):
    type = "vtp"
    model_cls = VTPAttributes