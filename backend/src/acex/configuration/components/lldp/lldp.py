
from acex.configuration.components.base_component import ConfigComponent
from acex.configuration.components.interfaces import Interface

from acex_devkit.models.composed_configuration import (
    LldpConfigAttributes,
    LldpInterfaceConfigAttributes,
    ReferenceFrom,
    ReferenceTo,
)

class LldpConfig(ConfigComponent): 
    type = "lldp_config"
    model_cls = LldpConfigAttributes

class LldpInterface(ConfigComponent): 
    type = "lldp_interface"
    model_cls = LldpInterfaceConfigAttributes

    def pre_init(self):
        # Resolve source_interface
        if "interface" in self.kwargs:
            si = self.kwargs.pop("interface")
            if isinstance(si, type(None)):
                pass
            elif isinstance(si, str):
                ref = ReferenceTo(pointer=f"interfaces.{si}")
                self.kwargs["interface"] = ref

            elif isinstance(si, Interface):
                ref = ReferenceTo(pointer=f"interfaces.{si.name}")
                self.kwargs["interface"] = ref