from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import FrontpanelPort, InterfaceTemplate


class ConfigureAccessPorts(ConfigMap):
    def compile(self, context):

        standard_template = InterfaceTemplate(
            name="Standard",
            description="Standard",
            storm_control={
                "broadcast_pps": 250,
                "multicast_pps": 1000,
                "unknown_unicast_pps": 200,
                "action": "trap",
            },
            stp_portfast=True,
            stp_bpdu_guard=True,
            stp_root_guard=True,
            switchport_mode="access",
            dtp_negotiation=False,
        )
        context.configuration.add(standard_template)

        ip_phone_template = InterfaceTemplate(
            name="IP_PHONE_INTERFACE_TEMPLATE",
            description="Voice Phone AutoConf",
            switchport_mode="access",
            switchport_nonegotiate=True,
            switchport_block_unicast=True,
            # no_switchport_port_security=True,
            storm_control_broadcast_level_pps=250,
            storm_control_multicast_level_pps=1000,
            storm_control_action="trap",
            # load_interval=30
        )
        context.configuration.add(ip_phone_template)

        lap_template = InterfaceTemplate(
            name="LAP_INTERFACE_TEMPLATE",
            description="Lightweight Access-Point AutoConf",
            switchport_mode="trunk",
            switchport_trunk_native_vlan=248,
            switchport_block_unicast=True,
            # no_switchport_port_security=True,
            storm_control_broadcast_level_pps=1000,
            storm_control_multicast_level_pps=2000,
            storm_control_action="trap",
            # load_interval=30
        )
        context.configuration.add(lap_template)

        # Nodes without a sequence fall back to their id
        ln = context.logical_node
        sequence = ln.sequence if ln.sequence is not None else ln.id

        max_no_of_stacks = 9

        for stack_index in range(max_no_of_stacks):
            for i in range(0, 48):
                access_port = FrontpanelPort(
                    name=f"access_port_{stack_index}_{i}",
                    index=i,
                    stack_index=stack_index,
                    module_index=0,
                    enabled=True,
                    switchport=True,
                    switchport_mode="access",
                    access_vlan=sequence + 10,
                    negotiation=False,
                    speed=10000000,
                    auto_mdix=False,
                    stp_portfast=True,
                    description=f"Access Port {i}",
                    interface_template=standard_template,
                    snmp_link_status_trap=False,
                    logging_link_status=False,
                )
                context.configuration.add(access_port)
            for i in range(0, 4):
                uplink_port = FrontpanelPort(
                    name=f"Uplink port {i}",
                    index=i,
                    stack_index=stack_index,
                    module_index=1,
                    enabled=True,
                    switchport=True,
                    switchport_mode="trunk",
                    negotiation=False,
                    speed=25000000,
                    auto_mdix=False,
                    stp_portfast=False,
                )
                context.configuration.add(uplink_port)


config = ConfigureAccessPorts()
config.filters = FilterAttribute("role").eq("lan_asw")
