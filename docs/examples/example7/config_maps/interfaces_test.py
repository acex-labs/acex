from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import FrontpanelPort, ManagementPort, Svi, LagInterface
from acex.configuration.components.network_instances import L3Vrf
from acex.configuration.components.network_instances import Vlan

interface_templates = {
    "default":{"native_vlan": 1,"description":"default","switchport":True,"switchport_mode":"access","enabled":True},
    "Mgmt":{"native_vlan": 2,"description":"Mgmt","switchport":True,"switchport_mode":"access","enabled":True},
    "Native":{"native_vlan": 999,"description":"Native","switchport":True,"switchport_mode":"access","enabled":True},
}

portchannel_list = [
    {'interface': 'Port-channel22', 'description':'switch2', 'index': 22, 'switchport': True, 'switchport_mode': 'trunk', "enabled": True, "native_vlan": 999, "members":["TwentyFiveGigE1/0/22","TwentyFiveGigE2/0/22"]},
]
interface_list = [
    {'interface': 'TwentyFiveGigE1/0/1', 'stack_index': 1, 'speed': 25000000, 'description': 'To-core-device', 'switchport': True, 'switchport_mode': 'trunk', 'index': 0, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/0/21', 'stack_index': 1, 'speed': 25000000, 'index': 20, '_template': 'Native'},
    {'interface': 'TwentyFiveGigE1/0/22', 'stack_index': 1, 'speed': 25000000, 'index': 21, '_template': 'Native', "etherchannel": "Port-channel22", "lacp_enabled":True, "lacp_mode":"active", "lacp_interval":"fast"},
    {'interface': 'TwentyFiveGigE1/0/23', 'stack_index': 1, 'speed': 25000000, 'index': 22, '_template': 'Native'},
    {'interface': 'TwentyFiveGigE2/0/21', 'stack_index': 2, 'speed': 25000000, 'index': 20, '_template': 'Native'},
    {'interface': 'TwentyFiveGigE2/0/22', 'stack_index': 2, 'speed': 25000000, 'index': 21, '_template': 'Native', "etherchannel": "Port-channel22", "lacp_enabled":True, "lacp_mode":"active", "lacp_interval":"fast"},
    {'interface': 'TwentyFiveGigE2/0/23', 'stack_index': 2, 'speed': 25000000, 'index': 22, '_template': 'Native'},
]

# Define each interface with a loop. This is just and example. If you want to keep it easy you can let the below logic be and only work
# with the interface list and templates above.
class Interfaces(ConfigMap):
    def compile(self, context):
        for portchannel in portchannel_list:
            portchannel = LagInterface(
                name = f'Port-channel{portchannel.get("index")}',
                index = portchannel.get("index"),
                description = portchannel.get("description"),
                switchport_mode = portchannel.get("switchport_mode"),
                switchport = portchannel.get("switchport"),
                native_vlan = portchannel.get("native_vlan"),
                enabled = portchannel.get("enabled"),
                members = portchannel.get("members")
            )
            context.configuration.add(portchannel)
        
        for intf in interface_list:
            interface = FrontpanelPort(
                name = intf.get("interface"),
                index = intf.get("index"),
                stack_index = intf.get("stack_index") if intf.get("stack_index") else None,
                mtu = intf.get('mtu') if intf.get('mtu') else None,
                speed = intf.get('speed') if intf.get('speed') else None,
                trunk_allowed_vlans = intf.get('trunk_allowed_vlans') if intf.get('trunk_allowed_vlans') else None, 
                enabled = interface_templates.get(intf.get("_template"), {}).get("enabled") or intf.get("enabled"),
                description = interface_templates.get(intf.get("_template"), {}).get("description") or intf.get("description"),
                switchport_mode = interface_templates.get(intf.get("_template"), {}).get("switchport_mode") or intf.get("switchport_mode"), 
                switchport = interface_templates.get(intf.get("_template"), {}).get("switchport") or intf.get("switchport"), 
                access_vlan = interface_templates.get(intf.get("_template"), {}).get("access_vlan") or intf.get("access_vlan"), 
                native_vlan = interface_templates.get(intf.get("_template"), {}).get("native_vlan") or intf.get("native_vlan"),
                aggregate_id = intf.get("etherchannel") if intf.get("etherchannel") else None,
                lacp_enabled = intf.get("lacp_enabled") if intf.get("lacp_enabled") else None,
                lacp_mode = intf.get("lacp_mode") if intf.get("lacp_mode") else None,
                lacp_interval = intf.get("lacp_interval") if intf.get("lacp_interval") else None
            )
            context.configuration.add(interface)

# Define a mgmt interface. A vrf is created and assigned to the mgmt interface. If you do not want to have a vrf binding on the
# mgmt interface you can skip the network_instance parameter when creating the ManagementPort instance.
class ManagementInterface(ConfigMap):
    def compile(self, context):
        vrf = L3Vrf(
            name="mgmt"
        )
        context.configuration.add(vrf)
    
        mgmt_port = ManagementPort(
            name='mgmt0',
            index=0,
            description='Management Port',
            enabled=True,
            #ipv4='192.168.1.1/24',
            network_instance=vrf
        )

        context.configuration.add(mgmt_port)

class SimpleVlan(ConfigMap):
    def compile(self, context):
        vlan_list = [
            {
                "vlan_name": "default",
                "vlan_id": 1
            },
            {
                "vlan_name": "Mgmt",
                "vlan_id": 2
            },
            {
                "vlan_name": "Native",
                "vlan_id": 999
            },
        ]

        # Don't touch this logic, just update list above.
        for _vlan in vlan_list:
            vlan = Vlan(
                #name = 'vlan_{}'.format(x['vlan_id'])
                name = f'vlan_{_vlan["vlan_id"]}',
                vlan_id = _vlan['vlan_id'],
                vlan_name = _vlan['vlan_name']
                )
            if _vlan["vlan_id"] == 2:
                svi2 = Svi(
                    name=f'vlan{str(_vlan["vlan_id"])}_svi',
                    description=_vlan['vlan_name'],
                    vlan=vlan,
                    index=0,
                    ipv4='192.168.1.1/24'
                )
                context.configuration.add(svi2)

            context.configuration.add(vlan)

vlan = SimpleVlan()
vlan.filters = FilterAttribute("site").eq("/.*/")

inter = Interfaces()
inter.filters = FilterAttribute("hostname").eq("/.*/")

mgmt = ManagementInterface()
mgmt.filters = FilterAttribute("hostname").eq("/.*/")