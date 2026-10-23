from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.services import Services


class SetServices(ConfigMap):
    def compile(self, context):
        services = Services(
            name="system_services",
            http=True,
            https=True,
        )

        context.configuration.add(services)


services = SetServices()
services.filters = (
    FilterAttribute("role").eq("access")
    | FilterAttribute("role").eq("distribution")
    | FilterAttribute("role").eq("core")
)
