from acex.configuration.components.base_component import ConfigComponent
from acex.models.composed_configuration import NtpServer as NtpServerAttributes

class NtpServer(ConfigComponent):
    type = "ntp_server"
    model_cls = NtpServerAttributes