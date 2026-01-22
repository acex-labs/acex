from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import FrontpanelPort, ManagementPort, Svi, LagInterface
from acex.configuration.components.network_instances import L3Vrf
from acex.configuration.components.network_instances import Vlan
from acex.configuration.components.lacp import LacpConfig
#from acex.configuration.components.spanning_tree import SpanningTreeGlobal

interface_templates = {
    "default":{"native_vlan": 1,"description":"default","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
    "Mgmt":{"native_vlan": 2,"description":"Mgmt","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
    "PC_FL0":{"native_vlan": 11,"description":"PC_FL0","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
    "PC_FL1":{"native_vlan": 12,"description":"PC_FL1","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
    "PC_FL2":{"native_vlan": 13,"description":"PC_FL2","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
    "PC_FL3":{"native_vlan": 14,"description":"PC_FL3","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
    "PC_FL4":{"native_vlan": 15,"description":"PC_FL4","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
    "Printer":{"native_vlan": 61,"description":"Printer","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
    "IFLEX":{"native_vlan": 91,"description":"IFLEX","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
    "DSL":{"native_vlan": 99,"description":"DSL","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
    "ECWiFi":{"native_vlan": 100,"description":"ECWiFi","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
    "FACTORY_DEVICES":{"native_vlan": 128,"description":"FACTORY_DEVICES","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
    "GUEST":{"native_vlan": 129,"description":"GUEST","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
    "Video":{"native_vlan": 150,"description":"Video","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
    "IoTwired":{"native_vlan": 601,"description":"IoTwired","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
    "Native":{"native_vlan": 999,"description":"Native","switchport":True,"switchport_mode":"access","enabled":True,"stp_portfast":True, "stp_bpdu_guard": True},
}

portchannel_list = [
    {'interface': 'Port-channel42', 'aggregate_id':42,'description':'CORE uplink', 'index': 1, 'switchport': True, 'switchport_mode': 'trunk', "enabled": True, "native_vlan": 123, "members":["TwentyFiveGigE1/1/1","TenGigabitEthernet2/1/1"]},
]

interface_list = [
    {'interface': 'TenGigabitEthernet1/0/1', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 0, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/2', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 1, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/3', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 2, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/4', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 3, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/5', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 4, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/6', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 5, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/7', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 6, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/8', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 7, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/9', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 8, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/10', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 9, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/11', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 10, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/12', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 11, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/13', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 12, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/14', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 13, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/15', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 14, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/16', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 15, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/17', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 16, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/18', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 17, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/19', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 18, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/20', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 19, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/21', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 20, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/22', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 21, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/23', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 22, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/24', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 23, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/25', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 24, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/26', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 25, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/27', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 26, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/28', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 27, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/29', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 28, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/30', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 29, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/31', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 30, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/32', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 31, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/33', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 32, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/34', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 33, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/35', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 34, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/36', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 35, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/37', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 36, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/38', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 37, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/39', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 38, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/40', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 39, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/41', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 40, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/42', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 41, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/43', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 42, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/44', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 43, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/45', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 44, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/46', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 45, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/47', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 46, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/0/48', 'speed': 10000000, 'module_index': 0, 'stack_index': 1, 'index': 47, '_template': 'PC_FL2'},
    {'interface': 'TenGigabitEthernet1/1/1', 'speed': 10000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 0, 'enabled': True},
    {'interface': 'TenGigabitEthernet1/1/2', 'speed': 10000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 1, 'enabled': True},
    {'interface': 'TenGigabitEthernet1/1/3', 'speed': 10000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 2, 'enabled': True},
    {'interface': 'TenGigabitEthernet1/1/4', 'speed': 10000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 3, 'enabled': True},
    {'interface': 'TenGigabitEthernet1/1/5', 'speed': 10000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 4, 'enabled': True},
    {'interface': 'TenGigabitEthernet1/1/6', 'speed': 10000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 5, 'enabled': True},
    {'interface': 'TenGigabitEthernet1/1/7', 'speed': 10000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 6, 'enabled': True},
    {'interface': 'TenGigabitEthernet1/1/8', 'speed': 10000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 7, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/1', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'index': 0, 'description':'Core Uplink','switchport_mode':'trunk','switchport': True, 'enabled':True, "aggregate_id": 42, "lacp_enabled":True, "lacp_mode":"active"},
    {'interface': 'TwentyFiveGigE1/1/2', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 1, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/3', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 2, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/4', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 3, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/5', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 4, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/6', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 5, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/7', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 6, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/8', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 7, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/9', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 8, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/10', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 9, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/11', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 10, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/12', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 11, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/13', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 12, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/14', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 13, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/15', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 14, 'enabled': True},
    {'interface': 'TwentyFiveGigE1/1/16', 'speed': 25000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 15, 'enabled': True},
    {'interface': 'HundredGigE1/1/1', 'speed': 100000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 0, 'enabled': True},
    {'interface': 'HundredGigE1/1/2', 'speed': 100000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 1, 'enabled': True},
    {'interface': 'HundredGigE1/1/3', 'speed': 100000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 2, 'enabled': True},
    {'interface': 'HundredGigE1/1/4', 'speed': 100000000, 'module_index': 1, 'stack_index': 1, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 3, 'enabled': True},
    {'interface': 'GigabitEthernet2/0/1', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 0, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/2', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 1, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/3', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 2, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/4', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 3, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/5', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 4, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/6', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 5, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/7', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 6, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/8', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 7, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/9', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 8, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/10', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 9, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/11', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 10, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/12', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 11, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/13', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 12, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/14', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 13, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/15', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 14, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/16', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 15, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/17', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 16, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/18', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 17, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/19', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 18, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/20', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 19, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/21', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 20, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/22', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 21, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/23', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 22, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/24', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 23, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/25', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 24, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/26', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 25, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/27', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 26, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/28', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 27, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/29', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 28, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/30', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 29, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/31', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 30, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/32', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 31, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/33', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 32, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/34', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 33, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/35', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 34, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/36', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 35, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/37', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 36, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/38', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 37, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/39', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 38, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/40', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 39, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/41', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 40, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/42', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 41, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/43', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 42, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/44', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 43, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/45', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 44, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/46', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 45, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/47', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 46, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/0/48', 'speed': 1000000, 'module_index': 0, 'stack_index': 2, 'index': 47, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet2/1/1', 'speed': 1000000, 'module_index': 1, 'stack_index': 2, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 0, 'enabled': True},
    {'interface': 'GigabitEthernet2/1/2', 'speed': 1000000, 'module_index': 1, 'stack_index': 2, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 1, 'enabled': True},
    {'interface': 'GigabitEthernet2/1/3', 'speed': 1000000, 'module_index': 1, 'stack_index': 2, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 2, 'enabled': True},
    {'interface': 'GigabitEthernet2/1/4', 'speed': 1000000, 'module_index': 1, 'stack_index': 2, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 3, 'enabled': True},
    {'interface': 'TenGigabitEthernet2/1/1', 'speed': 10000000, 'module_index': 1, 'stack_index': 2, 'index': 0, 'description':'Core Uplink','switchport_mode':'trunk','switchport': True, 'enabled':True, "aggregate_id": 42, "lacp_enabled":True, "lacp_mode":"active"},
    {'interface': 'TenGigabitEthernet2/1/2', 'speed': 10000000, 'module_index': 1, 'stack_index': 2, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 1, 'enabled': True},
    {'interface': 'TenGigabitEthernet2/1/3', 'speed': 10000000, 'module_index': 1, 'stack_index': 2, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 2, 'enabled': True},
    {'interface': 'TenGigabitEthernet2/1/4', 'speed': 10000000, 'module_index': 1, 'stack_index': 2, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 3, 'enabled': True},
    {'interface': 'TenGigabitEthernet2/1/5', 'speed': 10000000, 'module_index': 1, 'stack_index': 2, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 4, 'enabled': True},
    {'interface': 'TenGigabitEthernet2/1/6', 'speed': 10000000, 'module_index': 1, 'stack_index': 2, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 5, 'enabled': True},
    {'interface': 'TenGigabitEthernet2/1/7', 'speed': 10000000, 'module_index': 1, 'stack_index': 2, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 6, 'enabled': True},
    {'interface': 'TenGigabitEthernet2/1/8', 'speed': 10000000, 'module_index': 1, 'stack_index': 2, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 7, 'enabled': True},
    {'interface': 'FortyGigabitEthernet2/1/1', 'speed': 40000000, 'module_index': 1, 'stack_index': 2, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 0, 'enabled': True},
    {'interface': 'FortyGigabitEthernet2/1/2', 'speed': 40000000, 'module_index': 1, 'stack_index': 2, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 1, 'enabled': True},
    {'interface': 'TwentyFiveGigE2/1/1', 'speed': 25000000, 'module_index': 1, 'stack_index': 2, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 0, 'enabled': True},
    {'interface': 'TwentyFiveGigE2/1/2', 'speed': 25000000, 'module_index': 1, 'stack_index': 2, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 1, 'enabled': True},
    {'interface': 'GigabitEthernet3/0/1', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 0, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/2', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 1, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/3', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 2, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/4', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 3, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/5', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 4, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/6', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 5, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/7', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 6, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/8', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 7, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/9', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 8, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/10', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 9, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/11', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 10, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/12', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 11, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/13', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 12, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/14', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 13, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/15', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 14, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/16', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 15, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/17', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 16, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/18', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 17, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/19', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 18, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/20', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 19, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/21', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 20, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/22', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 21, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/23', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 22, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/0/24', 'speed': 1000000, 'module_index': 0, 'stack_index': 3, 'index': 23, '_template': 'PC_FL2'},
    {'interface': 'GigabitEthernet3/1/1', 'speed': 1000000, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 1, 'enabled': True},
    {'interface': 'GigabitEthernet3/1/2', 'speed': 1000000, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 2, 'enabled': True},
    {'interface': 'GigabitEthernet3/1/3', 'speed': 1000000, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 3, 'enabled': True},
    {'interface': 'GigabitEthernet3/1/4', 'speed': 1000000, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 4, 'enabled': True},
    {'interface': 'TenGigabitEthernet3/1/1', 'speed': 10000000, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 1, 'enabled': True},
    {'interface': 'TenGigabitEthernet3/1/2', 'speed': 10000000, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 2, 'enabled': True},
    {'interface': 'TenGigabitEthernet3/1/3', 'speed': 10000000, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 3, 'enabled': True},
    {'interface': 'TenGigabitEthernet3/1/4', 'speed': 10000000, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 4, 'enabled': True},
    {'interface': 'TenGigabitEthernet3/1/5', 'speed': 10000000, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 5, 'enabled': True},
    {'interface': 'TenGigabitEthernet3/1/6', 'speed': 10000000, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 6, 'enabled': True},
    {'interface': 'TenGigabitEthernet3/1/7', 'speed': 10000000, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 7, 'enabled': True},
    {'interface': 'TenGigabitEthernet3/1/8', 'speed': 10000000, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 8, 'enabled': True},
    {'interface': 'FortyGigabitEthernet3/1/1', 'speed': None, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 0, 'enabled': True},
    {'interface': 'FortyGigabitEthernet3/1/2', 'speed': None, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 1, 'enabled': True},
    {'interface': 'TwentyFiveGigE3/1/1', 'speed': None, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 0, 'enabled': True},
    {'interface': 'TwentyFiveGigE3/1/2', 'speed': None, 'module_index': 1, 'stack_index': 3, 'description': None, 'switchport': False, 'switchport_mode': None, 'index': 1, 'enabled': True},
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
                members = portchannel.get("members"),
                #stp = stp_intf_config
            )
            context.configuration.add(portchannel)
        
        for intf in interface_list:
            interface = FrontpanelPort(
                name = intf.get("interface"),
                index = intf.get("index"),
                stack_index = intf.get("stack_index") if intf.get("stack_index") else None,
                module_index = intf.get("module_index") if intf.get("module_index") else None,
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
                #stp_portfast = interface_templates.get(intf.get("_template"), {}).get("stp_portfast") or intf.get("stp_portfast"),
                #stp_bpdu_guard = interface_templates.get(intf.get("_template"), {}).get("stp_bpdu_guard") or intf.get("stp_bpdu_guard"),
            )
            context.configuration.add(interface)

class SimpleVlan(ConfigMap):
    def compile(self, context):
        # At the moment we need to define the vlan for mgmt SVI here as we otherweise can't make the connection.
        vlan = Vlan(
            name = 'vlan_1337', # You are allowed to change these stats. If ID changes, change name to "vlan_{ID}"
            vlan_id = 1337, # You are allowed to change these stats.
            vlan_name = 'Mgmt' # You are allowed to change these stats.
        )
        context.configuration.add(vlan)
        
        # Below is the mgmt vlan SVI
        svi2 = Svi(
            name=f'vlan2_svi', # You are allowed to change these stats. If ID changes, change name to "vlan{ID}_svi"
            description='Mgmt', # You are allowed to change these stats.
            vlan=vlan,
            index=0,
            ipv4='172.25.1.34/24' # You are allowed to change these stats
        )
        context.configuration.add(svi2)

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

class LACPConfig(ConfigMap):
    def compile(self, context):
        lacp = LacpConfig(
            system_priority=32768,
            #system_id_mac="00:1A:2B:3C:4D:5E",
            load_balance_algorithm=["src-ip", "dst-ip"] # Extended in Cisco language
            #load_balance_algorithm=["src-ip"] # Just normal
        )
        context.configuration.add(lacp)

vlan = SimpleVlan()
vlan.filters = FilterAttribute("site").eq("/.*/")

inter = Interfaces()
inter.filters = FilterAttribute("hostname").eq("/.*/")

mgmt = ManagementInterface()
mgmt.filters = FilterAttribute("hostname").eq("/.*/")

lacp = LACPConfig()
lacp.filters = FilterAttribute("hostname").eq("/.*/")