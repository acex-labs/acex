from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.aaa import (
    aaaServerGroup,
    aaaTacacs,
    aaaRadius,
    aaaAuthenticationMethods,
    aaaAuthorizationMethods,
    aaaAccountingMethods
)

from acex.configuration.components.interfaces import Svi
from acex.configuration.components.network_instances import Vlan

class TacacsConfig(ConfigMap):
    def compile(self, context):
        vlan = Vlan(
            name = 'vlan_1337', # You are allowed to change these stats. If ID changes, change name to "vlan_{ID}"
            vlan_id = 1337, # You are allowed to change these stats.
            vlan_name = 'Mgmt' # You are allowed to change these stats.
        )
        context.configuration.add(vlan)

        svi1337 = Svi(
            name='vlan1337_svi', # You are allowed to change these stats. If ID changes, change name to "vlan{ID}_svi"
            description='Mgmt', # You are allowed to change these stats.
            vlan=vlan,
            index=0,
            ipv4='172.25.1.34/24' # You are allowed to change these stats
        )
        context.configuration.add(svi1337)

        tacacs = aaaTacacs(
            name = "tacacs_server_1",
            port = 49,
            secret_key = 'MySecretKey',
            address = '10.10.10.1',
            source_interface = svi1337
        )
        context.configuration.add(tacacs)

        server_group = aaaServerGroup(
            name = 'TACACS_GROUP',
            enable = True,
            type = 'tacacs',
            tacacs = tacacs,
            radius = 'hej'
            #servers = ['10.10.10.1,172.16.23.1']
        )
        context.configuration.add(server_group)

class aaaConfig(ConfigMap):
    def compile(self, context):
        aaa_auth_methods = aaaAuthenticationMethods(
            name = 'AAA_AUTH_METHODS',
            method = ['TACACS_GROUP','LOCAL']
        )
        context.configuration.add(aaa_auth_methods)

        aaa_authorization_methods = aaaAuthorizationMethods(
            name = 'AAA_AUTHOR_METHODS',
            method = ['TACACS_GROUP','LOCAL']
        )
        context.configuration.add(aaa_authorization_methods)

        aaa_accounting_methods = aaaAccountingMethods(
            name = 'AAA_ACCOUNT_METHODS',
            method = ['TACACS_GROUP','LOCAL']
        )
        context.configuration.add(aaa_accounting_methods)

tacacs_config = TacacsConfig()
tacacs_config.filters = FilterAttribute("site").eq("/.*/")

aaa_config = aaaConfig()
aaa_config.filters = FilterAttribute("site").eq("/.*/")