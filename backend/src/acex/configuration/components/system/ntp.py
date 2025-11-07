from acex.configuration.components.base_component import ConfigComponent
<<<<<<< HEAD
from acex.models.ntp_server import NtpServerAttributes

class NtpServer(ConfigComponent):
    type = "ntp_server"
    model_cls = NtpServerAttributes
=======
from acex.models.ntp_server import NtpAttributes

class NTPServer(ConfigComponent):
    type = "ntp_server"
    model_cls = NtpAttributes
>>>>>>> 4ccc9e1 (Add support for ntp)
