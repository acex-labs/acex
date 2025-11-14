from acex.configuration.components.base_component import ConfigComponent
from acex.models.vlans import VlanAttributes

class Vlans(ConfigComponent):
    type = "vlans"
    model_cls = VlanAttributes