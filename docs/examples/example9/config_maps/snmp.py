from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.snmp import (
    SnmpGlobal,
    SnmpUser,
    SnmpServer,
    SnmpTrap
)
from acex.configuration.components.network_instances import L3Vrf
from acex.configuration.components.interfaces import Svi
from acex.configuration.components.network_instances import Vlan

class SNMPConfig(ConfigMap):
    def compile(self, context):
        snmp_global = SnmpGlobal(
            enabled = True,
            engine_id = "1234",
            location = "Data Center 1",
            contact = "noc@example.com"
        )
        context.configuration.add(snmp_global)

class SNMPUserConfig(ConfigMap):
    def compile(self, context):
        snmp_user = SnmpUser(
            username = "admin",
            auth_protocol = "SHA-512",
            auth_password = "authpass",
            priv_protocol = "AES256",
            priv_password = "privpass"
        )

        context.configuration.add(snmp_user)

class SNMPServerConfig(ConfigMap):
    def compile(self, context):
        enet_vrf = L3Vrf(
            name="ENET"
        )
        context.configuration.add(enet_vrf)

        vlan = Vlan(
            name = 'vlan_1337', # You are allowed to change these stats. If ID changes, change name to "vlan_{ID}"
            vlan_id = 1337, # You are allowed to change these stats.
            vlan_name = 'Mgmt' # You are allowed to change these stats.
        )
        context.configuration.add(vlan)

        svi1337 = Svi(
            name=f'vlan1337_svi', # You are allowed to change these stats. If ID changes, change name to "vlan{ID}_svi"
            description='Mgmt', # You are allowed to change these stats.
            vlan=vlan,
            index=0,
            ipv4='172.25.1.34/24' # You are allowed to change these stats
        )
        context.configuration.add(svi1337)

        snmp_server = SnmpServer(
            address = "192.168.123.123",
            port = 162,
            community = "public",
            version = "v3",
            source_interface = svi1337,
            network_instance = enet_vrf
        )

        context.configuration.add(snmp_server)

class SnmpTrapsConfig(ConfigMap):
    def compile(self, context):

        vrf_up = SnmpTrap(
            event_name = 'vrf-up'
        )
        context.configuration.add(vrf_up)

        vrf_down = SnmpTrap(
            event_name = 'vrf-down'
        )
        context.configuration.add(vrf_down)

snmp_server = SNMPServerConfig()
snmp_server.filters = FilterAttribute("site").eq("/.*/")

snmp_user = SNMPUserConfig()
snmp_user.filters = FilterAttribute("site").eq("/.*/")

snmp = SNMPConfig()
snmp.filters = FilterAttribute("site").eq("/.*/")

snmp_traps = SnmpTrapsConfig()
snmp_traps.filters = FilterAttribute("site").eq("/.*/")