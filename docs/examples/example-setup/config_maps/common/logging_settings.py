from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.logging import (
    RemoteServer,
    Console,
    LoggingConfig,
    VtyLine,
    FileLogging
)
from acex.configuration.components.acl import Ipv4Acl, Ipv4AclEntry

from acex.configuration.components.augments.cisco.archive import CiscoArchive
from acex.configuration.components.augments.cisco import (
    CiscoLoggingTrap,
    CiscoLoggingConsole,
    CiscoLoggingSsh
)

from acex.configuration.components.augments.cisco.cisco_aaa import (
    CiscoConsoleAaa,
    CiscoVtyAaa,
)

from config_maps.common.aaa import (
    AAA_AUTH_LOGIN_LIST,
    AAA_AUTHZ_EXEC_LIST,
    AAA_AUTHZ_CONSOLE_EXEC_LIST,
    AAA_AUTHZ_CONSOLE_COMMANDS_LIST,
)

class GlobalConfig(ConfigMap):
    def compile(self, context):

        global_config = LoggingConfig(
            buffer_size=65536,
            severity='INFORMATIONAL',
        )    
        context.configuration.add(global_config)

class RemoteServerConfig(ConfigMap):
    def compile(self, context):

        remote_server1 = RemoteServer(
            name='srv1.example.net',
            host='10.10.10.123',
            source_address='Vlan2' # Can be an IP address or an interface reference
        )
        context.configuration.add(remote_server1)

        remote_server2 = RemoteServer(
            name='srv2.example.net',
            host='10.10.10.124',
            #source_interface='vlan3'
        )
        context.configuration.add(remote_server2)

class ConsoleConfig(ConfigMap):
    def compile(self, context):

        console_line0 = Console(
            name='line con 0',
            line_number=0,
            logging_synchronous=True
        )    
        context.configuration.add(console_line0)

        console_aaa = CiscoConsoleAaa(
            name="console_aaa",
            login_authentication=AAA_AUTH_LOGIN_LIST,
            authorization_exec=AAA_AUTHZ_CONSOLE_EXEC_LIST,
            authorization_commands=AAA_AUTHZ_CONSOLE_COMMANDS_LIST,
            target=console_line0,
        )
        context.configuration.add(console_aaa)

class VtyConfig(ConfigMap):

    def compile(self, context):

        # VTY ACL
        # ip access-list standard RESTRICT_VRF_VTY_ACL
        # permit any
        vty_acl = Ipv4Acl(
            name="RESTRICT_VRF_VTY_ACL"
        )
        context.configuration.add(vty_acl)
        
        vty_acl_entry = Ipv4AclEntry(
            name="RESTRICT_VRF_VTY_ACL_entry",
            ipv4_acl=vty_acl,
            action="permit",
            ipv4acl=vty_acl
        )
        context.configuration.add(vty_acl_entry)

        for line in range(0,15):
            vty_line = VtyLine(
                    name=f'line_vty{line}',
                    line_number=line,
                    logging_synchronous=True,
                    transport_input='ssh',
                    ipv4acl=vty_acl
                )
            context.configuration.add(vty_line)

class FileLoggingConfig(ConfigMap):
    def compile(self, context):

        file_logging = FileLogging(
            name='file logging',
            #file_size=10485760, # 10MB
            #severity='INFORMATIONAL',
            files=10
        )
        context.configuration.add(file_logging)
        
        archive_config = CiscoArchive(
            name='archive1',
            enabled=True,
            log_config=True,
            path='flash:',
            write_memory=True,
            target=file_logging
        )
        context.configuration.add(archive_config)
        
class SetCiscoLogging(ConfigMap):
    def compile(self, context):

        traplogging = CiscoLoggingTrap(
            #name="traplogging",
            severity="NOTICE",
            target=LoggingConfig(),
        )

        context.configuration.add(traplogging)
        
        traplogging = CiscoLoggingConsole(
            #name="consolelogging",
            enabled=False,
            target=LoggingConfig(),
        )

        context.configuration.add(traplogging)
        
        traplogging = CiscoLoggingSsh(
            #name="sshlogging",
            enabled=True,
            target=LoggingConfig(),
        )

        context.configuration.add(traplogging)

global_config = GlobalConfig()
global_config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
remote_server_config = RemoteServerConfig()
remote_server_config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
console_config = ConsoleConfig()
console_config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
vty_config = VtyConfig()
vty_config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
file_logging_config = FileLoggingConfig()
file_logging_config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
cisco_logging_config = SetCiscoLogging()
cisco_logging_config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)