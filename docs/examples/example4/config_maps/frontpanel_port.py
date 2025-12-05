from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import FrontPanelPort, ManagementPort
from acex.configuration.components.network_instances import L3Vrf


interface_templates = {
    "default": {'description': None, 'switchport': False, 'switchport_mode': None, 'enabled': True}, # Portar utan template = default?
    "mgmt": {'description': 'LAN_Management', 'switchport': True, 'switchport_mode': 'access', 'switchport_untagged_vlan': 2, 'enabled': True},
    "print": {'description': 'Printers', 'switchport': True, 'switchport_mode': 'access', 'switchport_untagged_vlan': 61, 'enabled': True},
    "guest": {'description': 'GUEST', 'switchport': True, 'switchport_mode': 'access', 'switchport_untagged_vlan': 129, 'enabled': True},
    "iotwired": {'description': 'IoTWired', 'switchport': True, 'switchport_mode': 'access', 'switchport_untagged_vlan': 601, 'enabled': True},
}

interface_list = [    
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
        'interface':'Port-1/0/27',
        'index': 34,
        '_template': 'mgmt'
    },
    {
        'interface':'Port-1/0/28',
        'index': 35,
        '_template': 'mgmt'
    },
    {
        'interface':'Port-1/0/29',
        'index': 36,
        '_template': 'mgmt'
    },
    {
        'interface':'Port-1/0/30',
        'index': 37,
        '_template': 'mgmt'
    },
    {
        'interface':'Port-1/0/31',
        'index': 38,
        '_template': 'mgmt'
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

class Interfaces(ConfigMap):
    def compile(self, context):
        # Specific ports
        for intf in interface_list:

            interface = FrontPanelPort(
                name = intf["interface"],
                index = intf["index"],
                enabled = interface_templates.get(intf.get("_template", {}), {}).get("enabled") or intf.get("enabled", False),
                description = interface_templates.get(intf.get("_template", {}), {}).get("description"),
                switchport_mode = interface_templates.get(intf.get("_template", {}), {}).get("switchport_mode") or intf.get("switchport_mode"),
                switchport = interface_templates.get(intf.get("_template", {}), {}).get("switchport") or intf.get("switchport"),
                access_vlan = interface_templates.get(intf.get("_template", {}), {}).get("access_vlan") or intf.get("access_vlan"),
                native_vlan = interface_templates.get(intf.get("_template", {}), {}).get("native_vlan") or intf.get("native_vlan")
                )
            context.configuration.add(interface)

        # Standard ports below. Only change if a port is removed from the loop.
        # Standard ports for PCs
        for i in range(0,23): # stack 1?
            # 1/0/1 - 1/0/24
            accessport = FrontPanelPort(
                name=f'port-{i}',
                index=i,
                description='accessport',
                enabled=True,
                switchport_mode='access',
                switchport=True,
                native_vlan=10
            )

            context.configuration.add(accessport)
        
        for i in range(32,47):  # stack 1?
            # 1/0/33 - 1/0/48 
            accessport = FrontPanelPort(
                name=f'port-{i}',
                index=i,
                description='accessport',
                enabled=True,
                switchport_mode='access',
                switchport=True,
                native_vlan=10
            )

            context.configuration.add(accessport)

        trunk1 = FrontPanelPort(
            name='trunk-1',
            # 1/1/3
            index=51,
            description='To core',
            switchport_mode='trunk',
            switchport=True,
            native_vlan=123,
            enabled=True
        )

        context.configuration.add(trunk1)

        trunk2 = FrontPanelPort(
            name='trunk-2',
            # 4/1/3
            index=223, # ???
            description='To core',
            switchport_mode='trunk',
            switchport=True,
            native_vlan=123,
            enabled=True
        )

        context.configuration.add(trunk2)

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