from acex.configuration.components.base_component import ConfigComponent
from acex.models.ntp_server import NTPServerAttributes

class NTPServer(ConfigComponent):
    type = "ntp_server"
    model_cls = NTPServerAttributes