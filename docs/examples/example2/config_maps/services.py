from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.services import Services

class SetServices(ConfigMap):
    def compile(self, context):
        services = Services(
            name="system_services",
            http=True, # activate http
            https=True, # activate https
        )

        context.configuration.add(services)

services = SetServices()
services.filters = FilterAttribute("site").eq("CML")