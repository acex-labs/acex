from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import FrontpanelPort, ManagementPort
from acex.configuration.components.network_instances import L3Vrf


interface_templates = {
    "default": {'description': None, 'switchport': False, 'switchport_mode': None, 'enabled': False},
    "mgmt": {'description': 'LAN_Management', 'switchport': True, 'switchport_mode': 'access', 'switchport_untagged_vlan': 2, 'enabled': True},
    "print": {'description': 'Printers', 'switchport': True, 'switchport_mode': 'access', 'switchport_untagged_vlan': 61, 'enabled': True},
    "guest": {'description': 'GUEST', 'switchport': True, 'switchport_mode': 'access', 'switchport_untagged_vlan': 129, 'enabled': True},
    "iotwired": {'description': 'IoTWired', 'switchport': True, 'switchport_mode': 'access', 'switchport_untagged_vlan': 601, 'enabled': True},
}

interface_list = [
    {
        'interface': 'Port-1/0/1',
        'index': 8,
        '_template': 'print'
    },
    {
        'interface': 'Port-1/0/2',
        'index': 9,
        '_template': 'default'
    },
    {
        'interface':'Port-1/0/25',
        'index': 32,
        '_template': 'mgmt'
    },
    {
        'interface':'Port-1/0/26',
        'index': 33,
        '_template': 'mgmt'
    },
    {
        'interface':'Port-1/0/31',
        'index': 38,
        '_template': 'mgmt'
    },
    {
        'interface':'Port-1/0/48',
        'index': 55,
        'switchport': True,
        'switchport_mode': 'trunk',
        'native_vlan': 123,
        'enabled': True,
        'speed': 10000000,
        'description': 'Uplink to Core',
        'trunk_allowed_vlans': [10,20,30,40,50,60,61,70,80,90,100,110,120,123,129],
        'mtu': 9216
    },
    {
        'interface':'Port-2/0/1',
        'index': 63,
        '_template': 'guest'
    },
    {
        'interface':'Port-2/0/12',
        'index': 74,
        '_template': 'iotwired'
    },
    {
        'interface':'Port-2/0/34',
        'index': 96,
        '_template': 'iotwired'
    }
]

# Define each interface with a loop. This is just and example. If you want to keep it easy you can let the below logic be and only work
# with the interface list and templates above.
class Interfaces(ConfigMap):
    def compile(self, context):
        for intf in interface_list:

            interface = FrontpanelPort(
                name = intf.get("interface"),
                index = intf.get("index"),
                mtu = intf.get('mtu') if intf.get('mtu') else None,
                speed = intf.get('speed') if intf.get('speed') else None,
                trunk_allowed_vlans = intf.get('trunk_allowed_vlans') if intf.get('trunk_allowed_vlans') else None, 
                enabled = interface_templates.get(intf.get("_template"), {}).get("enabled") or intf.get("enabled"),
                description = interface_templates.get(intf.get("_template"), {}).get("description") or intf.get("description"),
                switchport_mode = interface_templates.get(intf.get("_template"), {}).get("switchport_mode") or intf.get("switchport_mode"), 
                switchport = interface_templates.get(intf.get("_template"), {}).get("switchport") or intf.get("switchport"), 
                access_vlan = interface_templates.get(intf.get("_template"), {}).get("access_vlan") or intf.get("access_vlan"), 
                native_vlan = interface_templates.get(intf.get("_template"), {}).get("native_vlan") or intf.get("native_vlan") 
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
            ipv4='192.168.1.1/24',
            network_instance=vrf
        )

        context.configuration.add(mgmt_port)

inter = Interfaces()
inter.filters = FilterAttribute("hostname").eq("/.*/")

mgmt = ManagementInterface()
mgmt.filters = FilterAttribute("hostname").eq("/.*/")