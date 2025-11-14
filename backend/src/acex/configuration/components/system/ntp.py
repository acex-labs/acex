from acex.configuration.components.base_component import ConfigComponent
from acex.models.ntp_server import NtpServerAttributes

class NtpServer(ConfigComponent):
    type = "ntp_server"
    model_cls = NtpServerAttributes