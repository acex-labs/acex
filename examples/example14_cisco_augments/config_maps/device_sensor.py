from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.augments.cisco import (
    CiscoDeviceSensorFilterList,
    CiscoDeviceSensorFilterSpec,
    CiscoDeviceSensorNotify,
)


class SetDeviceSensor(ConfigMap):
    def compile(self, context):
        lldp_list = CiscoDeviceSensorFilterList(
            name="my_lldp_list",
            protocol="lldp",
            items=["system-name", "system-description"],
        )
        context.configuration.add(lldp_list)
        context.configuration.add(CiscoDeviceSensorFilterSpec(filter_list=lldp_list))

        dhcp_list = CiscoDeviceSensorFilterList(
            name="my_dhcp_list",
            protocol="dhcp",
            items=[
                "host-name",
                "default-ip-ttl",
                "requested-address",
                "parameter-request-list",
                "class-identifier",
                "client-identifier",
            ],
        )
        context.configuration.add(dhcp_list)
        context.configuration.add(CiscoDeviceSensorFilterSpec(filter_list=dhcp_list))

        cdp_list = CiscoDeviceSensorFilterList(
            name="my_cdp_list",
            protocol="cdp",
            items=["device-name", "address-type", "capabilities-type", "platform-type"],
        )
        context.configuration.add(cdp_list)
        context.configuration.add(CiscoDeviceSensorFilterSpec(filter_list=cdp_list))

        context.configuration.add(CiscoDeviceSensorNotify(all_changes=True))


config = SetDeviceSensor()
config.filters = FilterAttribute("role").eq("/.*/")
