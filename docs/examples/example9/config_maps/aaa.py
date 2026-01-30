from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.aaa import (
    aaaServerGroup,
    aaaTacacs,
    aaaRadius,
    aaaAuthenticationMethods,
    aaaAuthorizationMethods,
    aaaAuthorizationEvents,
    aaaAccountingMethods,
    aaaAccountingEvents
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
            source_interface = svi1337 # Could be a reference to an interface, or just an IP.
        )
        context.configuration.add(tacacs)

        tacacs2 = aaaTacacs(
            name = "tacacs_server_2",
            port = 49,
            secret_key = 'MySecretKey',
            address = '10.123.132.1',
            source_interface = svi1337 # Could be a reference to an interface, or just an IP.
        )
        context.configuration.add(tacacs2)

        radius = aaaRadius(
            name = "radius_server_1",
            port = 49,
            secret_key = 'radiusSomeSecretKey',
            address = '172.16.23.54',
            source_interface = svi1337 # Could be a reference to an interface, or just an IP.
        )
        context.configuration.add(radius)

        radius2 = aaaRadius(
            name = "radius_server_2",
            port = 49,
            secret_key = 'radiusSecretKey',
            address = '172.16.12.123',
            source_interface = svi1337 # Could be a reference to an interface, or just an IP.
        )
        context.configuration.add(radius2)

        server_group = aaaServerGroup(
            name = 'TACACS_GROUP',
            enable = True,
            type = 'tacacs',
            tacacs = [tacacs, tacacs2],
            radius = radius
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

        aaa_authorization_events = aaaAuthorizationEvents(
            name = 'AAA_AUTHOR_EVENTS',
            events = ['config-commands','console','interactive-commands']
        )
        context.configuration.add(aaa_authorization_events)

        aaa_accounting_methods = aaaAccountingMethods(
            name = 'AAA_ACCOUNT_METHODS',
            method = ['TACACS_GROUP','LOCAL']
        )
        context.configuration.add(aaa_accounting_methods)

        aaa_accounting_events = aaaAccountingEvents(
            name = 'AAA_ACCOUNT_EVENTS',
            events = ['send','cstop-record','authentication']
        )
        context.configuration.add(aaa_accounting_events)

tacacs_config = TacacsConfig()
tacacs_config.filters = FilterAttribute("site").eq("/.*/")

aaa_config = aaaConfig()
aaa_config.filters = FilterAttribute("site").eq("/.*/")