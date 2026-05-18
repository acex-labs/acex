from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.services import Services
from acex.configuration.components.augments.cisco.access_session import (
    CiscoAccessSession,
    AccessSessionFilterList,
    AccessSessionAccountingSpec,
    AccessSessionAuthenticationSpec,
)


class SetServices(ConfigMap):
    def compile(self, context):
        services = Services(
            name="system_services",
            http=True,  # activate http
            https=True,  # activate https
        )

        context.configuration.add(services)

        acct_list = AccessSessionFilterList(
            items=["cdp", "lldp", "dhcp", "http"],
        )

        auth_list = AccessSessionFilterList(
            items=["vlan-id"],
        )

        acct_spec = AccessSessionAccountingSpec(
            action="include",
            filter_list="Def_Acct_List",
        )

        auth_spec = AccessSessionAuthenticationSpec(
            action="include",
            filter_list="Def_Auth_List",
        )

        access_session = CiscoAccessSession(
            name="access_session",
            target=services,
            filter_lists={
                "Def_Acct_List": acct_list,
                "Def_Auth_List": auth_list,
            },
            accounting=acct_spec,
            authentication=auth_spec,
        )
        context.configuration.add(access_session)


services = SetServices()
services.filters = FilterAttribute("site").eq("/.*/")
