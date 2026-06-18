from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.aaa import (
    aaaGlobal,
    aaaServerGroup,
    aaaTacacs,
    aaaRadius,
    aaaAuthenticationMethods,
    aaaAuthenticationConfig,
    aaaAuthorizationConfig,
    aaaAccountingConfig,
    aaaAuthorizationMethods,
    aaaAuthorizationEvents,
    aaaAccountingMethods,
    aaaAccountingEvents
)
from acex.configuration.components.augments.cisco.cisco_aaa import CiscoAaaAuthentication, CiscoAaaAuthorization, CiscoAaaAccounting

class aaaconfig(ConfigMap):
    def compile(self, context):
        aaa_global = aaaGlobal(
            name = 'AAA_GLOBAL',
            enabled = True
        )
        context.configuration.add(aaa_global)
        
        
class aaaAuthConfig(ConfigMap):
    def compile(self, context):
        #----------------------------------------------------------#
        # Authentication method list for login or enable.
        #----------------------------------------------------------#
        aaa_auth_config = aaaAuthenticationConfig(name='CONSOLE-AUTH')
        context.configuration.add(aaa_auth_config)
        
        method_list = ['local', 'line', 'enable']
        cisco_aaa = CiscoAaaAuthentication(
            name=aaa_auth_config.name,
            methods=method_list,
            auth_type='login',
            target=aaa_auth_config
            #group=
        )
        context.configuration.add(cisco_aaa)

class aaaAuthzConfig(ConfigMap):
    def compile(self, context):
        #----------------------------------------------------------#
        # Authorization method list for exec or commands.
        #----------------------------------------------------------#
        #Authorization method list for exec or commands.
        #Ex. command:
        #aaa authorization exec default group ISE-TACACS+ local 
        #aaa authorization exec CONSOLE-CUSTOM-AUTHORIZATION-LIST none 
        #aaa authorization exec CONSOLE-EXEC none
        #aaa authorization commands 0 default group ISE-TACACS+ local 
        #aaa authorization commands 0 CONSOLE-CUSTOM-COMMAND-AUTHORIZATION-LIST none 
        #aaa authorization commands 0 CONSOLE-COMMANDS none 
        #aaa authorization commands 1 default group ISE-TACACS+ local 
        #aaa authorization commands 1 CONSOLE-CUSTOM-COMMAND-AUTHORIZATION-LIST none 
        #aaa authorization commands 1 CONSOLE-COMMANDS none 
        #aaa authorization commands 15 default group ISE-TACACS+ local 
        #aaa authorization commands 15 CONSOLE-CUSTOM-COMMAND-AUTHORIZATION-LIST none 
        #aaa authorization commands 15 CONSOLE-COMMANDS none 
        
        aaa_authz_default_config = aaaAuthorizationConfig(name='default')
        context.configuration.add(aaa_authz_default_config)
        aaa_authz_console_exec_config = aaaAuthorizationConfig(name='CONSOLE-EXEC')
        context.configuration.add(aaa_authz_console_exec_config)
        aaa_auth_custom_console_config = aaaAuthorizationConfig(name='CONSOLE-CUSTOM-COMMAND-AUTHORIZATION-LIST')
        context.configuration.add(aaa_auth_custom_console_config)
    
        cisco_aaa_default_authz = CiscoAaaAuthorization(
            name=aaa_authz_default_config.name,
            author_type='exec',
            group='ISE-TACACS+', # reference?
            methods=['local'],
            target=aaa_authz_default_config
        )
        context.configuration.add(cisco_aaa_default_authz)
    
        aaa_authz_console_exec = CiscoAaaAuthorization(
            name=aaa_authz_console_exec_config.name,
            author_type='exec',
            methods=['none'],
            target=aaa_authz_console_exec_config
        )
        context.configuration.add(aaa_authz_console_exec)
        
        aaa_authz_custom_console = CiscoAaaAuthorization(
            name=aaa_auth_custom_console_config.name,
            author_type='exec',
            methods=['none'],
            target=aaa_auth_custom_console_config
        )
        context.configuration.add(aaa_authz_custom_console)
        
        for i, priv_level in enumerate([0, 1, 15]):
            custom_command_authz = CiscoAaaAuthorization(
                name=f"{aaa_auth_custom_console_config.name}_{i}",
                author_type='commands',
                methods=['none'],
                target=aaa_auth_custom_console_config,
                privilege_level=priv_level
            )
            context.configuration.add(custom_command_authz)
        
class aaaAcctConfig(ConfigMap):
    def compile(self, context):
        #----------------------------------------------------------#
        # Accounting method list for login or enable.
        #----------------------------------------------------------#
        aaa_acct_config = aaaAccountingConfig(name='CONSOLE-ACCT')
        context.configuration.add(aaa_acct_config)
        
        cisco_aaa_acct = CiscoAaaAccounting(
            name=aaa_acct_config.name,
            account_type='exec',
            target=aaa_acct_config
        )
        context.configuration.add(cisco_aaa_acct)
        
aaa_config = aaaconfig()
aaa_config.filters = FilterAttribute("site").eq("/.*/")

aaa_auth_config = aaaAuthConfig()
aaa_auth_config.filters = FilterAttribute("site").eq("/.*/")

aaa_authz_config = aaaAuthzConfig()
aaa_authz_config.filters = FilterAttribute("site").eq("/.*/")
#
#aaa_acct_config = aaaAcctConfig()
#aaa_acct_config.filters = FilterAttribute("site").eq("/.*/")