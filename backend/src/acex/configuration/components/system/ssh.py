from acex.configuration.components.base_component import ConfigComponent
from acex.models.ssh_server import SshAttributes

class SshServer(ConfigComponent):
    type = "ssh_server"
    model_cls = SshAttributes