from acex.configuration.components.base_component import ConfigComponent
<<<<<<< HEAD
<<<<<<< HEAD
from acex.models.ntp_server import NtpServerAttributes

class NtpServer(ConfigComponent):
    type = "ntp_server"
    model_cls = NtpServerAttributes
=======
from acex.models.ntp_server import NtpAttributes
=======
from acex.models.ntp_server import NtpServerAttributes
>>>>>>> 3fccc02 (Changed so that variable and class names follow pascal/peb8 standard)

class NtpServer(ConfigComponent):
    type = "ntp_server"
<<<<<<< HEAD
    model_cls = NtpAttributes
>>>>>>> 4ccc9e1 (Add support for ntp)
=======
    model_cls = NtpServerAttributes
>>>>>>> 3fccc02 (Changed so that variable and class names follow pascal/peb8 standard)
