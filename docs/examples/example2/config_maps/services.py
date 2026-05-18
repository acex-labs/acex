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

        #filter_list_options = CiscoAccessSessionFilterListOption(
        #    name="access_session_options",
        #    target=services,
        #    item="cdp"
        #)
        #context.configuration.add(filter_list_options)

        access_session_accounting_list = CiscoAccessSessionFilterList(
            name="Def_Acct_List",
            target=services,
            items=["cdp", "lldp", "dhcp", "http"]
        )

        context.configuration.add(access_session_accounting_list)
        
        access_session_auth_list = CiscoAccessSessionFilterList(
            name="Def_Auth_List",
            target=services,
            items=["vlan-id"]
        )

        context.configuration.add(access_session_auth_list)

services = SetServices()
services.filters = FilterAttribute("site").eq("/.*/")