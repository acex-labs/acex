from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import DnsServerAttributes

class DnsServer(ConfigComponent): 
    type = "dns_server"
    model_cls = DnsServerAttributes

    def pre_init(self):
        network_instance = self.kwargs.pop("network_instance", None)
        if network_instance is None:
            self.kwargs["network_instance"] = "global"
        elif isinstance(network_instance, str):
            self.kwargs["network_instance"] = network_instance
        else:
            self.kwargs["network_instance"] = network_instance.name