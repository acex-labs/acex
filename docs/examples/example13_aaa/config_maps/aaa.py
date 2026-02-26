from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.aaa import (
    aaaGlobal,
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

class aaaGlobalConfig(ConfigMap):
    def compile(self, context):
        aaa_global = aaaGlobal(
            name = 'AAA_GLOBAL',
            enabled = True
        )
        context.configuration.add(aaa_global)

class TacacsConfig(ConfigMap):
    def compile(self, context):
        aaa_server_group = aaaServerGroup(
            name = 'TACACS_GROUP',
            enable = True,
            type = 'tacacs',
        )
        context.configuration.add(aaa_server_group)
        
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
            source_interface = svi1337, # Could be a reference to an interface, or just an IP.
            server_group = aaa_server_group
        )
        context.configuration.add(tacacs)

        tacacs2 = aaaTacacs(
            name = "tacacs_server_2",
            port = 49,
            secret_key = 'MySecretKey',
            address = '10.123.132.1',
            source_interface = svi1337, # Could be a reference to an interface, or just an IP.
            server_group = aaa_server_group
        )
        context.configuration.add(tacacs2)

        radius = aaaRadius(
            name = "radius_server_1",
            port = 49,
            secret_key = 'radiusSomeSecretKey',
            address = '172.16.23.54',
            source_interface = svi1337, # Could be a reference to an interface, or just an IP.
            server_group = aaa_server_group

        )
        context.configuration.add(radius)

        radius2 = aaaRadius(
            name = "radius_server_2",
            port = 49,
            secret_key = 'radiusSecretKey',
            address = '172.16.12.123',
            source_interface = svi1337, # Could be a reference to an interface, or just an IP.
            server_group = aaa_server_group
        )
        context.configuration.add(radius2)

class aaaConfig(ConfigMap):
    def compile(self, context):
        method_list = ['TACACS_GROUP','LOCAL']
        for method in method_list:
            aaa_auth_method = aaaAuthenticationMethods(
                name = f'AAA_AUTH_METHOD_{method}',
                method = method
            )
            context.configuration.add(aaa_auth_method)

            authorization_method = aaaAuthorizationMethods(
                name = f'AAA_AUTHOR_METHOD_{method}',
                method = method
            )
            context.configuration.add(authorization_method)

            accounting_method = aaaAccountingMethods(
                name = f'AAA_ACCOUNT_METHOD_{method}',
                method = method
            )
            context.configuration.add(accounting_method)

        author_events = ['config-commands','console','interactive-commands']
        for event in author_events:
             aaa_authorization_events = aaaAuthorizationEvents(
                name = f'AAA_AUTHOR_EVENT_{event}',
                event = event
            )
             context.configuration.add(aaa_authorization_events)

        accounting_events = ['send','stop-record','authentication']
        for event in accounting_events:
            aaa_accounting_events = aaaAccountingEvents(
                name = f'AAA_ACCOUNT_EVENT_{event}',
                event = event
            )
            context.configuration.add(aaa_accounting_events)
        
        #aaa_auth_methods = aaaAuthenticationMethods(
        #    name = 'AAA_AUTH_METHODS',
        #    #method = ['TACACS_GROUP','LOCAL']
        #    method = 'TACACS_GROUP'
        #)
        #context.configuration.add(aaa_auth_methods)
#
        #authorization_method1 = aaaAuthorizationMethods(
        #    name = 'AAA_AUTHOR_METHOD_TACACS',
        #    #method = ['TACACS_GROUP','LOCAL']
        #    method = 'TACACS_GROUP'
        #)
        #context.configuration.add(authorization_method1)
        #authorization_method2 = aaaAuthorizationMethods(
        #    name = 'AAA_AUTHOR_METHOD_LOCAL',
        #    #method = ['TACACS_GROUP','LOCAL']
        #    method = 'LOCAL'
        #)
        #context.configuration.add(authorization_method2)

        #aaa_authorization_events = aaaAuthorizationEvents(
        #    name = 'AAA_AUTHOR_EVENTS',
        #    #events = ['config-commands','console','interactive-commands']
        #    event = 'config-commands'
        #)
        #context.configuration.add(aaa_authorization_events)
#
        #aaa_accounting_methods = aaaAccountingMethods(
        #    name = 'AAA_ACCOUNT_METHODS',
        #    method = ['TACACS_GROUP','LOCAL']
        #)
        #context.configuration.add(aaa_accounting_methods)
#
        #aaa_accounting_events = aaaAccountingEvents(
        #    name = 'AAA_ACCOUNT_EVENTS',
        #    events = ['send','cstop-record','authentication']
        #)
        #context.configuration.add(aaa_accounting_events)

global_config = aaaGlobalConfig()
global_config.filters = FilterAttribute("site").eq("/.*/")

tacacs_config = TacacsConfig()
tacacs_config.filters = FilterAttribute("site").eq("/.*/")

aaa_config = aaaConfig()
aaa_config.filters = FilterAttribute("site").eq("/.*/")