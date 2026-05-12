from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.augments.cisco.device_sensor import CiscoDeviceSensor
from acex.configuration.components.augments.cisco.access_session import (
    CiscoAccessSession,
)
from acex.configuration.components.system.services import ServicesConfig


class DeviceSensorConfig(ConfigMap):
    def compile(self, context):

        # Target node for the augments
        services_config = ServicesConfig()
        context.configuration.add(services_config)

        # -- device-sensor augment -----------------------------------------
        device_sensor = CiscoDeviceSensor(
            name="device_sensor",
            target=services_config,
            filter_lists={
                "my_lldp_list": {
                    "protocol": "lldp",
                    "items": ["system-name", "system-description"],
                },
                "my_dhcp_list": {
                    "protocol": "dhcp",
                    "items": [
                        "host-name",
                        "default-ip-ttl",
                        "requested-address",
                        "parameter-request-list",
                        "class-identifier",
                        "client-identifier",
                    ],
                },
                "my_cdp_list": {
                    "protocol": "cdp",
                    "items": [
                        "device-name",
                        "address-type",
                        "capabilities-type",
                        "platform-type",
                    ],
                },
            },
            filter_specs={
                "lldp_spec": {
                    "protocol": "lldp",
                    "action": "include",
                    "filter_list": "my_lldp_list",
                },
                "dhcp_spec": {
                    "protocol": "dhcp",
                    "action": "include",
                    "filter_list": "my_dhcp_list",
                },
                "cdp_spec": {
                    "protocol": "cdp",
                    "action": "include",
                    "filter_list": "my_cdp_list",
                },
            },
            notify="all-changes",
        )
        context.configuration.add(device_sensor)

        # -- access-session augment ----------------------------------------
        access_session = CiscoAccessSession(
            name="access_session",
            target=services_config,
            attribute_filter_lists={
                "Def_Acct_List": {
                    "items": ["cdp", "lldp", "dhcp", "http"],
                },
                "Def_Auth_List": {
                    "items": ["vlan-id"],
                },
            },
            authentication_filter_spec={
                "action": "include",
                "filter_list": "Def_Auth_List",
            },
            accounting_filter_spec={
                "action": "include",
                "filter_list": "Def_Acct_List",
            },
        )
        context.configuration.add(access_session)


device_sensor_config = DeviceSensorConfig()
device_sensor_config.filters = FilterAttribute("site").eq("/.*/")
