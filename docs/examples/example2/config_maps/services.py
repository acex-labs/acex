from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.services import Services
from acex.configuration.components.augments.cisco.access_session import (
    CiscoAccessSessionFilterList,
    CiscoAccessSessionFilterListOption
)

class SetServices(ConfigMap):
    def compile(self, context):
        services = Services(
            name="system_services",
            http=True, # activate http
            https=True, # activate https
        )

        context.configuration.add(services)

        filter_list_options = CiscoAccessSessionFilterListOption(
            name="access_session_options",
            target=services,
            item="cdp"
        )
        context.configuration.add(filter_list_options)

        access_session = CiscoAccessSessionFilterList(
            name="access_session",
            target=services,
        )

        context.configuration.add(access_session)

services = SetServices()
services.filters = FilterAttribute("site").eq("/.*/")