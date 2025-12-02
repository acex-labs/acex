from acex.configuration.components.base_component import ConfigComponent
from acex.models.composed_configuration import (
    AuthorizedKey, 
    SshServer as SshServerAttributes
)

class SshServer(ConfigComponent):
    type = "ssh_server"
    model_cls = SshServerAttributes

    def pre_init(self):
        print(self.kwargs)


class AuthorizedKey(ConfigComponent):
    type = "authorized_key"
    model_cls = AuthorizedKey