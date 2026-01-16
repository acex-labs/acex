from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import FrontpanelPort, ManagementPort, Svi, LagInterface
from acex.configuration.components.network_instances import L3Vrf
from acex.configuration.components.network_instances import Vlan
from acex.configuration.components.lacp import LacpConfig

interface_templates = {
    "default":{"native_vlan": 1,"description":"default","switchport":True,"switchport_mode":"access","enabled":True},
    "Mgmt":{"native_vlan": 1337,"description":"Mgmt","switchport":True,"switchport_mode":"access","enabled":True},
    "IoTwired":{"native_vlan": 123,"description":"IoTwired","switchport":True,"switchport_mode":"access","enabled":True},
    "Native":{"native_vlan": 999,"description":"Native","switchport":True,"switchport_mode":"access","enabled":True},
}

portchannel_list = [
    {'interface': 'Port-channel22', 'aggregate_id':22,'description':'switch2', 'index': 22, 'switchport': True, 'switchport_mode': 'trunk', "enabled": True, "native_vlan": 999, "members":["TwentyFiveGigE1/0/22","TwentyFiveGigE2/0/22"]},
]
interface_list = [
    {'interface': 'TwentyFiveGigE1/0/1', 'stack_index': 1, 'module_index':0, 'speed': 25000000, 'description': 'To-PRI-core-Device', 'switchport': True, 'switchport_mode': 'trunk', 'index': 0, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/0/2', 'stack_index': 1, 'module_index':0, 'speed': 25000000, 'index': 1, '_template': 'Server'},
    {'interface': 'TwentyFiveGigE1/0/3', 'stack_index': 1, 'module_index':0, 'speed': 25000000, 'index': 2, '_template': 'Server'},
    {'interface': 'TwentyFiveGigE1/0/20', 'stack_index': 1, 'module_index':0, 'speed': 25000000, 'index': 19, '_template': 'Native'},
    {'interface': 'TwentyFiveGigE1/0/21', 'stack_index': 1, 'module_index':0, 'speed': 25000000, 'index': 20, '_template': 'Native'},
    {'interface': 'TwentyFiveGigE1/0/22', 'stack_index': 1, 'module_index':0, 'speed': 25000000, 'index': 21, '_template': 'Native', "aggregate_id": 22, "lacp_enabled":True, "lacp_mode":"active", "lacp_interval":"fast", "lacp_port_priority": 1000},
    {'interface': 'TwentyFiveGigE1/0/23', 'stack_index': 1, 'module_index':0, 'speed': 25000000, 'index': 22, '_template': 'Native'},
    {'interface': 'TwentyFiveGigE1/0/24', 'stack_index': 1, 'module_index':0, 'speed': 25000000, 'index': 23, '_template': 'IoTwired'},
    {'interface': 'TwentyFiveGigE1/0/25', 'stack_index': 1, 'module_index':0, 'speed': 25000000, 'index': 24, '_template': 'Native'},
    {'interface': 'TenGigabitEthernet1/1/1', 'speed': 10000000, 'description': None, 'switchport': False, 'switchport_mode': None, 'module_index': 1, 'stack_index': 1, 'index': 0, 'enabled': True},
    {'interface': 'TenGigabitEthernet1/1/2', 'speed': 10000000, 'description': None, 'switchport': False, 'switchport_mode': None, 'module_index': 1, 'stack_index': 1, 'index': 1, 'enabled': True},
    {'interface': 'TenGigabitEthernet1/1/3', 'speed': 10000000, 'description': None, 'switchport': False, 'switchport_mode': None, 'module_index': 1, 'stack_index': 1, 'index': 2, 'enabled': True},
    {'interface': 'TenGigabitEthernet1/1/4', 'speed': 10000000, 'description': None, 'switchport': False, 'switchport_mode': None, 'module_index': 1, 'stack_index': 1, 'index': 3, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/1', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'index': 0, '_template': 'Native', "aggregate_id": 1, "lacp_enabled":True, "lacp_mode":"active", "lacp_interval":"fast"},
    {'interface': 'TwentyFiveGigE1/1/2', 'speed': 25000000, 'description': None, 'switchport': False, 'switchport_mode': None, 'module_index': 1, 'stack_index': 1, 'index': 1, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/3', 'speed': 25000000, 'description': None, 'switchport': False, 'switchport_mode': None, 'module_index': 1, 'stack_index': 1, 'index': 2, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/4', 'speed': 25000000, 'description': None, 'switchport': False, 'switchport_mode': None, 'module_index': 1, 'stack_index': 1, 'index': 3, 'enabled': True},
    {'interface': 'HundredGigE1/1/1', 'speed': 100000000, 'description': None, 'switchport': False, 'switchport_mode': None, 'module_index': 1, 'stack_index': 1, 'index': 0, 'enabled': True},
    {'interface': 'HundredGigE1/1/2', 'speed': 100000000, 'description': None, 'switchport': False, 'switchport_mode': None, 'module_index': 1, 'stack_index': 1, 'index': 1, 'enabled': True},
    {'interface': 'HundredGigE1/1/3', 'speed': 100000000, 'description': None, 'switchport': False, 'switchport_mode': None, 'module_index': 1, 'stack_index': 1, 'index': 2, 'enabled': True},
    {'interface': 'HundredGigE1/1/4', 'speed': 100000000, 'description': None, 'switchport': False, 'switchport_mode': None, 'module_index': 1, 'stack_index': 1, 'index': 3, 'enabled': True},
    {'interface': 'TwentyFiveGigE2/0/2', 'stack_index': 2, 'module_index':0, 'speed': 25000000, 'index': 1, '_template': 'Server'},
    {'interface': 'TwentyFiveGigE2/0/3', 'stack_index': 2, 'module_index':0, 'speed': 25000000, 'index': 2, '_template': 'Native'},
    {'interface': 'TwentyFiveGigE2/0/18', 'stack_index': 2, 'module_index':0, 'speed': 25000000, 'index': 17, '_template': 'Native'},
    {'interface': 'TwentyFiveGigE2/0/19', 'stack_index': 2, 'module_index':0, 'speed': 25000000, 'index': 18, '_template': 'Native'},
    {'interface': 'TwentyFiveGigE2/0/20', 'stack_index': 2, 'module_index':0, 'speed': 25000000, 'index': 19, '_template': 'IoTwired'},
    {'interface': 'TwentyFiveGigE2/0/21', 'stack_index': 2, 'module_index':0, 'speed': 25000000, 'index': 20, '_template': 'Native'},
    {'interface': 'TwentyFiveGigE2/0/22', 'stack_index': 2, 'module_index':0, 'speed': 25000000, 'index': 21, '_template': 'Native', "aggregate_id": 22, "lacp_enabled":True, "lacp_mode":"active", "lacp_interval":"fast"},
    {'interface': 'TwentyFiveGigE2/0/23', 'stack_index': 2, 'module_index':0, 'speed': 25000000, 'index': 22, '_template': 'Native'},
    {'interface': 'TwentyFiveGigE2/0/24', 'stack_index': 2, 'module_index':0, 'speed': 25000000, 'index': 23, '_template': 'IoTwired'},
    {'interface': 'GigabitEthernet2/1/1', 'speed': 1000000, 'description': None, 'switchport': False, 'switchport_mode': None, 'module_index': 1, 'stack_index': 2, 'index': 0, 'enabled': True, "aggregate_id": 1, "lacp_enabled":True, "lacp_mode":"active", "lacp_interval":"fast"},
    {'interface': 'GigabitEthernet2/1/2', 'speed': 1000000, 'description': None, 'switchport': False, 'switchport_mode': None, 'module_index': 1, 'stack_index': 2, 'index': 1, 'enabled': True},
    {'interface': 'GigabitEthernet2/1/3', 'speed': 1000000, 'description': None, 'switchport': False, 'switchport_mode': None, 'module_index': 1, 'stack_index': 2, 'index': 2, 'enabled': True},
    {'interface': 'GigabitEthernet2/1/4', 'speed': 1000000, 'description': None, 'switchport': False, 'switchport_mode': None, 'module_index': 1, 'stack_index': 2, 'index': 3, 'enabled': True},
]

# Define each interface with a loop. This is just and example. If you want to keep it easy you can let the below logic be and only work
# with the interface list and templates above.
class Interfaces(ConfigMap):
    def compile(self, context):
        for portchannel in portchannel_list:
            portchannel = LagInterface(
                name = f'Port-channel{portchannel.get("index")}',
                aggregate_id = portchannel.get("aggregate_id"),
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
                module_index = intf.get("module_index"),
                mtu = intf.get('mtu') if intf.get('mtu') else None,
                speed = intf.get('speed') if intf.get('speed') else None,
                trunk_allowed_vlans = intf.get('trunk_allowed_vlans') if intf.get('trunk_allowed_vlans') else None, 
                enabled = interface_templates.get(intf.get("_template"), {}).get("enabled") or intf.get("enabled"),
                description = interface_templates.get(intf.get("_template"), {}).get("description") or intf.get("description"),
                switchport_mode = interface_templates.get(intf.get("_template"), {}).get("switchport_mode") or intf.get("switchport_mode"), 
                switchport = interface_templates.get(intf.get("_template"), {}).get("switchport") or intf.get("switchport"), 
                access_vlan = interface_templates.get(intf.get("_template"), {}).get("access_vlan") or intf.get("access_vlan"), 
                native_vlan = interface_templates.get(intf.get("_template"), {}).get("native_vlan") or intf.get("native_vlan"),
                aggregate_id = intf.get("aggregate_id") if intf.get("aggregate_id") else None,
                lacp_enabled = intf.get("lacp_enabled") if intf.get("lacp_enabled") else None,
                lacp_mode = intf.get("lacp_mode") if intf.get("lacp_mode") else None,
                #lacp_interval = intf.get("lacp_interval") if intf.get("lacp_interval") else None
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
            #ipv4='10.10.10.1/24',
            network_instance=vrf
        )

        context.configuration.add(mgmt_port)

class LACPConfig(ConfigMap):
    def compile(self, context):
        lacp = LacpConfig(
            system_priority=32768,
            #system_id_mac="00:1A:2B:3C:4D:5E",
            load_balance_algorithm=["src-ip", "dst-ip"] # Extended in Cisco language
            #load_balance_algorithm=["src-ip"] # Just normal
        )
        context.configuration.add(lacp)

class SimpleVlan(ConfigMap):
    def compile(self, context):
        # At the moment we need to define the vlan for mgmt SVI here as we otherweise can't make the connection.
        vlan = Vlan(
            name = 'vlan_2', # You are allowed to change these stats. If ID changes, change name to "vlan_{ID}"
            vlan_id = 2, # You are allowed to change these stats.
            vlan_name = 'Mgmt' # You are allowed to change these stats.
        )
        context.configuration.add(vlan)
        
        # Below is the mgmt vlan SVI
        svi2 = Svi(
            name=f'vlan2_svi', # You are allowed to change these stats. If ID changes, change name to "vlan{ID}_svi"
            description='Mgmt', # You are allowed to change these stats.
            vlan=vlan,
            index=0,
            ipv4='192.168.1.1/24' # You are allowed to change these stats
        )
        context.configuration.add(svi2)

vlan = SimpleVlan()
vlan.filters = FilterAttribute("site").eq("/.*/")

inter = Interfaces()
inter.filters = FilterAttribute("hostname").eq("/.*/")

mgmt = ManagementInterface()
mgmt.filters = FilterAttribute("hostname").eq("/.*/")

lacp = LACPConfig()
lacp.filters = FilterAttribute("hostname").eq("/.*/")