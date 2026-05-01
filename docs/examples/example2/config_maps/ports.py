from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import FrontpanelPort, InterfaceTemplate
from acex.configuration.components.augments import (
    CiscoDeviceTrackingPolicy,
    CiscoServicePolicy,
)


class ConfigureAccessPorts(ConfigMap):
    def compile(self, context):

        # Reusable template for the LAN access ports.
        # Shared attributes go here; per-port stuff (name, index, stack_index, module_index)
        # stays on the FrontpanelPort instance below.
        standard_template = InterfaceTemplate(
            name="Standard",
            description="Standard",
            switchport_mode="access",
            dtp_negotiation=False,
            stp_portfast=True,
            stp_bpdu_guard=True,
            storm_control={
                "broadcast_pps": 250,
                "multicast_pps": 1000,
                "unknown_unicast_pps": 200,
                "action": "trap",
            },
        )
        context.configuration.add(standard_template)

        # Cisco-specific extension: AutoQoS service-policy attachment on the template.
        # Inherited by every port that uses the template.
        context.configuration.add(CiscoServicePolicy(
            name="standard_autoqos",
            target=standard_template,
            input_policy="AutoQos-4.0-Trust-Dscp-Input-Policy",
            output_policy="AutoQos-4.0-Output-Policy",
        ))

        for stack_index in range(1, 3):
            for i in range(1, 48):
                access_port = FrontpanelPort(
                    name=f"access_port_{stack_index}_{i}",
                    index=i,
                    stack_index=stack_index,
                    module_index=1,
                    access_vlan=12,
                    speed=10000000,
                    interface_template=standard_template,
                )
                context.configuration.add(access_port)

                # Cisco-specific extension: per-port device-tracking attachment.
                context.configuration.add(CiscoDeviceTrackingPolicy(
                    name=f"access_port_{stack_index}_{i}_ipdt",
                    target=access_port,
                    policy_name="IPDT_POLICY",
                ))


config = ConfigureAccessPorts()
config.filters = FilterAttribute("role").eq("lan_access")
