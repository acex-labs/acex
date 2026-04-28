from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import SflowCollectorAttributes, RstpAttributes, MstpAttributes, MstpInstanceAttributes, RapidPVSTAttributes

class SflowCollector(ConfigComponent): 
    type = "SflowCollector"
    model_cls = SflowCollectorAttributes