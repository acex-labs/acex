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
        #tacacs group example
        tacacs = aaaServerGroup(
            name = 'ISE-TACACS+',
            enable = True,
            type = 'tacacs',
        )
        context.configuration.add(tacacs)
        
        radius = aaaServerGroup(
            name = 'RADIUS-GROUP-NEW',
            enable = True,
            type = 'radius',
        )
        context.configuration.add(radius)
        
        """
        Example:
        aaa authentication login default group ISE-TACACS+ local
        aaa authentication login CONSOLE-CUSTOM-AUTHENTICATION-LIST local line enable
        aaa authentication login CONSOLE-AUTHENTICATION local line enable
        aaa authentication enable default group ISE-TACACS+ enable
        aaa authentication dot1x default group RADIUS-GROUP-NEW
        """
        #----------------------------------------------------------#
        # Authentication method list for login or enable.
        #----------------------------------------------------------#
        aaa_default_auth_config = aaaAuthenticationConfig(name='default')
        context.configuration.add(aaa_default_auth_config)
        # LOGIN #
        default_aaa_login = CiscoAaaAuthentication(
            name=f"{aaa_default_auth_config.name}_LOGIN",
            methods=[tacacs.name, 'local'],
            auth_type='login',
            group_type='tacacs+',
            group_name=tacacs,#'ISE-TACACS+', # reference?
            target=aaa_default_auth_config
        )
        context.configuration.add(default_aaa_login)
        # ENABLE #
        default_aaa_enable = CiscoAaaAuthentication(
            name=f"{aaa_default_auth_config.name}_ENABLE",
            methods=[radius.name, 'enable'],
            auth_type='enable',
            group_type='tacacs+',
            group_name=tacacs,#'ISE-TACACS+', # reference?
            target=aaa_default_auth_config
        )
        context.configuration.add(default_aaa_enable)
        
        # DOT1X #
        default_aaa_dot1x = CiscoAaaAuthentication(
            name=f"{aaa_default_auth_config.name}_DOT1X",
            #methods=['dot1x'],
            auth_type='dot1x',
            group_type='radius',
            group_name=radius,#'RADIUS-GROUP-NEW', # reference?
            target=aaa_default_auth_config
        )
        context.configuration.add(default_aaa_dot1x)
        
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

#class aaaAuthzConfig(ConfigMap):
#    def compile(self, context):
        #----------------------------------------------------------#
        # Authorization method list for exec or commands.
        #----------------------------------------------------------#
        """
        Authorization method list for exec or commands.
        Ex. command:
        aaa authorization exec default group ISE-TACACS+ local 
        aaa authorization exec CONSOLE-CUSTOM-AUTHORIZATION-LIST none 
        aaa authorization exec CONSOLE-EXEC none
        aaa authorization commands 0 default group ISE-TACACS+ local 
        aaa authorization commands 0 CONSOLE-CUSTOM-COMMAND-AUTHORIZATION-LIST none 
        aaa authorization commands 0 CONSOLE-COMMANDS none 
        aaa authorization commands 1 default group ISE-TACACS+ local 
        aaa authorization commands 1 CONSOLE-CUSTOM-COMMAND-AUTHORIZATION-LIST none 
        aaa authorization commands 1 CONSOLE-COMMANDS none 
        aaa authorization commands 15 default group ISE-TACACS+ local 
        aaa authorization commands 15 CONSOLE-CUSTOM-COMMAND-AUTHORIZATION-LIST none 
        aaa authorization commands 15 CONSOLE-COMMANDS none 
        """
        
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
        
#class aaaAcctConfig(ConfigMap):
#    def compile(self, context):
        #----------------------------------------------------------#
        # Accounting method list for login or enable.
        #----------------------------------------------------------#
        """
        aaa accounting update newinfo periodic 2880
        aaa accounting identity default start-stop group RADIUS-GROUP-NEW
        aaa accounting exec default start-stop group ISE-TACACS+
        aaa accounting commands 0 default start-stop group ISE-TACACS+
        aaa accounting commands 1 default start-stop group ISE-TACACS+
        aaa accounting commands 15 default start-stop group ISE-TACACS+
        """
        aaa_acct_default_config = aaaAccountingConfig(name='default')
        context.configuration.add(aaa_acct_default_config) 

        cisco_aaa_acct_identity_default = CiscoAaaAccounting(
            name=f"{aaa_acct_default_config.name}_IDENTITY",
            account_type='identity',
            group_name=radius, # reference?
            group_type='radius',
            methods=['start-stop'],
            target=aaa_acct_default_config
        )
        context.configuration.add(cisco_aaa_acct_identity_default)
        
        cisco_aaa_acct_exec_default = CiscoAaaAccounting(
            name=f"{aaa_acct_default_config.name}_EXEC",
            account_type='exec',
            group_name=tacacs, # reference?
            group_type='tacacs+',
            methods=['start-stop'],
            target=aaa_acct_default_config
        )
        context.configuration.add(cisco_aaa_acct_exec_default)
        
        for i, priv in enumerate([0, 1, 15]):
            cisco_aaa_acct_commands = CiscoAaaAccounting(
                name=f"{aaa_acct_default_config.name}_COMMANDS_{i}",
                account_type='commands',
                group_name=tacacs, # reference?
                group_type='tacacs+',
                methods=['start-stop'],
                privilege_level=priv,
                target=aaa_acct_default_config
            )
            context.configuration.add(cisco_aaa_acct_commands)
            
        cisco_aaa_acct_default = CiscoAaaAccounting(
            name=aaa_acct_default_config.name,
            account_type='exec',
            group_name=tacacs, # reference?
            group_type='tacacs+',
            methods=['start-stop'],
            target=aaa_acct_default_config
        )
        context.configuration.add(cisco_aaa_acct_default)
        
aaa_config = aaaconfig()
aaa_config.filters = FilterAttribute("site").eq("/.*/")

aaa_auth_config = aaaAuthConfig()
aaa_auth_config.filters = FilterAttribute("site").eq("/.*/")

#aaa_authz_config = aaaAuthzConfig()
#aaa_authz_config.filters = FilterAttribute("site").eq("/.*/")
#
#aaa_acct_config = aaaAcctConfig()
#aaa_acct_config.filters = FilterAttribute("site").eq("/.*/")