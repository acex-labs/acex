from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.logging import (
    RemoteServer,
    Console,
    LoggingConfig,
    FileLogging,
    VtyLine,
)

from acex.configuration.components.augments.cisco.archive import CiscoArchive

from acex.configuration.components.acl import Ipv4Acl, Ipv4AclEntry

from acex.configuration.components.augments.cisco.cisco_aaa import (
    CiscoConsoleAaa,
    CiscoVtyAaa,
)

from config_maps.aaa import (
    AAA_AUTH_LOGIN_LIST,
    AAA_AUTHZ_EXEC_LIST,
    AAA_AUTHZ_CONSOLE_EXEC_LIST,
    AAA_AUTHZ_CONSOLE_COMMANDS_LIST,
)


class GlobalConfig(ConfigMap):
    def compile(self, context):

        global_config = LoggingConfig(
            buffer_size=65536,
        )

        context.configuration.add(global_config)


class RemoteServerConfig(ConfigMap):
    def compile(self, context):

        remote_server1 = RemoteServer(
            name="logg-server1.test.net",
            host="123.123.123.123",
            port=514,  # default 514, does not have to be defined
            transport="udp",  # default udp, does not have to be defined
            source_address="vlan2",  # Can be an IP address or an interface reference
        )
        context.configuration.add(remote_server1)

        remote_server2 = RemoteServer(
            name="logg-server2.test.net",
            host="234.234.234.234",
            port=514,  # default 514, does not have to be defined
            transport="udp",  # default udp, does not have to be defined
            # source_interface='vlan3'
        )
        context.configuration.add(remote_server2)


class ConsoleConfig(ConfigMap):
    def compile(self, context):

        console_line0 = Console(
            name="line con 0", line_number=0, logging_synchronous=True
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
        # ACL FOR VTY
        ipv4acl = Ipv4Acl(name="vty_acl", type="standard")
        context.configuration.add(ipv4acl)

        ipv4aclentry = Ipv4AclEntry(
            name="entry1",
            ipv4_acl=ipv4acl,
            action="permit",
            source_address="any",
            sequence_id=10,
        )
        context.configuration.add(ipv4aclentry)

        for line in range(0, 4):
            vty_line = VtyLine(
                name=f"line_vty{line}",
                line_number=line,
                logging_synchronous=True,
                ipv4acl=ipv4acl,
                acl_direction="in",
                # acl_network_instance='test'
            )
            context.configuration.add(vty_line)

            vty_aaa = CiscoVtyAaa(
                name=f"vty{line}_aaa",
                login_authentication=AAA_AUTH_LOGIN_LIST,
                authorization_exec=AAA_AUTHZ_EXEC_LIST,
                target=vty_line,
            )
            context.configuration.add(vty_aaa)


class FileLoggingConfig(ConfigMap):
    def compile(self, context):

        file_logging = FileLogging(
            name="logfile1",
            filename="/var/log/messages",
            rotate=5,  # Juniper specific, how many files to keep before rotating oldest file
            max_size=20480,  # Max size in bytes. Used both for Cisco and Juniper
            min_size=1024,  # Only used for Cisco
            facility="DAEMON",
            severity="INFORMATIONAL",
        )

        context.configuration.add(file_logging)

        archive_config = CiscoArchive(
            name="archive1",
            enabled=True,
            log_config=True,
            path="flash:",
            write_memory=True,
            rollback_filter=True,
            rollback_retry=60,
            # maximum=5,
            # time_period=1440,
            target=file_logging,
        )
        context.configuration.add(archive_config)


globalconfig = GlobalConfig()
globalconfig.filters = FilterAttribute("hostname").eq("/.*/")

remoteserverconfig = RemoteServerConfig()
remoteserverconfig.filters = FilterAttribute("hostname").eq("/.*/")

consoleconfig = ConsoleConfig()
consoleconfig.filters = FilterAttribute("hostname").eq("/.*/")

vtyconfig = VtyConfig()
vtyconfig.filters = FilterAttribute("hostname").eq("/.*/")

fileloggingconfig = FileLoggingConfig()
fileloggingconfig.filters = FilterAttribute("hostname").eq("/.*/")
