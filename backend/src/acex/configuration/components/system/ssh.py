from acex.configuration.components.base_component import ConfigComponent
from acex.models.composed_configuration import SshServer as SshServerAttributes

class SshServer(ConfigComponent):
    type = "ssh_server"
    model_cls = SshServerAttributes