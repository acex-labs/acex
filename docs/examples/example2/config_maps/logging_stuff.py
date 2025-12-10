from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.logging import (
    LoggingServer,
    LoggingConsole,
    LoggingConfig,
    FileConfig,
    VtyLines
)

class GlobalConfig(ConfigMap):
    def compile(self, context):

        global_config = LoggingConfig(
            buffer_size=65536,
        )
    
        context.configuration.add(global_config)

class LoggingServerConfig(ConfigMap):
    def compile(self, context):

        remote_server1 = LoggingServer(
            name='logg-server1.test.net',
            host='123.123.123.123',
            port=514, # default 514, does not have to be defined
            transport='udp', # default udp, does not have to be defined
            source_address='vlan2' # Can be an IP address or an interface reference
        )
        context.configuration.add(remote_server1)

        remote_server2 = LoggingServer(
            name='logg-server2.test.net',
            host='234.234.234.234',
            port=514, # default 514, does not have to be defined
            transport='udp', # default udp, does not have to be defined
            #source_interface='vlan3'
        )
        context.configuration.add(remote_server2)

class ConsoleConfig(ConfigMap):
    def compile(self, context):

        console_line0 = LoggingConsole(
            name='line con 0',
            line_number=0,
            logging_synchronous=True
        )
    
        context.configuration.add(console_line0)

class VtyConfig(ConfigMap):

    def compile(self, context):

        for line in range(0,4):
            vty_line = VtyLines(
                    name=f'line_vty{line}',
                    line_number=line,
                    logging_synchronous=True
                )
            context.configuration.add(vty_line)

class FileLoggingConfig(ConfigMap):
    def compile(self, context):

        file_config = FileConfig(
            name='logfile1',
            filename='/var/log/messages',
            files=5, # Juniper specific
            max_size=20480, # Max size in bytes. Used both for Cisco and Juniper
            min_size=1024, # Only used for Cisco
            facility='DAEMON',
            severity='INFORMATIONAL'
        )
    
        context.configuration.add(file_config)

loggingserverconfig = LoggingServerConfig()
loggingserverconfig.filters = FilterAttribute("hostname").eq("/.*/")

consoleconfig = ConsoleConfig()
consoleconfig.filters = FilterAttribute("hostname").eq("/.*/")

vtyconfig = VtyConfig()
vtyconfig.filters = FilterAttribute("hostname").eq("/.*/")

globalconfig = GlobalConfig()
globalconfig.filters = FilterAttribute("hostname").eq("/.*/")

fileloggingconfig = FileLoggingConfig()
fileloggingconfig.filters = FilterAttribute("hostname").eq("/.*/")