from acex.configuration.components.base_component import ConfigComponent
from acex.configuration.components.interfaces import Interface
from acex.models.composed_configuration import (
    AuthorizedKey, 
    ReferenceTo,
    SshServer as SshServerAttributes
)


class SshServer(ConfigComponent):
    type = "ssh_server"
    model_cls = SshServerAttributes

    def pre_init(self):
        # Resolve source_interface
        if "source_interface" in self.kwargs:
            si = self.kwargs.pop("source_interface")
            if isinstance(si, type(None)):
                pass
            elif isinstance(si, str):
                ref = ReferenceTo(pointer=f"interfaces.{si}")
                self.kwargs["source_interface"] = ref

            elif isinstance(si, Interface):
                ref = ReferenceTo(pointer=f"interfaces.{si.name}")
                self.kwargs["source_interface"] = ref



class AuthorizedKey(ConfigComponent):
    type = "authorized_key"
    model_cls = AuthorizedKey