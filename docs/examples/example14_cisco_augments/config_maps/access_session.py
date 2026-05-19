from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.augments.cisco import (
    CiscoAccessSessionFilterList,
    CiscoAccessSessionAuthentication
)

from acex.configuration.components.system.services import Services

class SetAccessSession(ConfigMap):
    def compile(self, context):
        fl = CiscoAccessSessionFilterList(
            items=["cdp", "lldp", "dhcp", "http"]
        )
        context.configuration.add(fl)

        access_session_auth = CiscoAccessSessionAuthentication(
            filter_lists=[fl]
        )
        context.configuration.add(access_session_auth)




config = SetAccessSession()
config.filters = FilterAttribute("role").eq("/.*/")