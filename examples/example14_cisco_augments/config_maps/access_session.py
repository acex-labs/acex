from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.augments.cisco import (
    CiscoAccessSessionFilterList,
    CiscoAccessSessionAccounting,
    CiscoAccessSessionAuthentication
)

from acex.configuration.components.system.services import Services

class SetAccessSession(ConfigMap):
    def compile(self, context):
        fl_acct = CiscoAccessSessionFilterList(
            name="Def_Acct_List",
            items=["cdp", "lldp", "dhcp", "http"]
        )
        context.configuration.add(fl_acct)

        access_session_auth = CiscoAccessSessionAuthentication(
            filter_lists=[fl_acct]
        )
        context.configuration.add(access_session_auth)


        fl_auth = CiscoAccessSessionFilterList(
            name="Def_Auth_List",
            items=["vlan-id"]
        )
        context.configuration.add(fl_auth)

        access_session_acct = CiscoAccessSessionAccounting(
            filter_lists=[fl_acct]
        )
        context.configuration.add(access_session_acct)





config = SetAccessSession()
config.filters = FilterAttribute("role").eq("/.*/")