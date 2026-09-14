from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.logging import (
    RemoteServer,
    Console,
    LoggingConfig,
    VtyLine
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
            name='logg-server1.test.net',
            host='123.123.123.123',
            source_address='vlan1337' # Can be an IP address or an interface reference
        )
        context.configuration.add(remote_server1)

        remote_server2 = RemoteServer(
            name='logg-server2.test.net',
            host='123.123.123.124',
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

class VtyConfig(ConfigMap):

    def compile(self, context):

        for line in range(0,15):
            vty_line = VtyLine(
                    name=f'line_vty{line}',
                    line_number=line,
                    logging_synchronous=True
                )
            context.configuration.add(vty_line)

remoteserverconfig = RemoteServerConfig()
remoteserverconfig.filters = FilterAttribute("site").eq("/.*/")

consoleconfig = ConsoleConfig()
consoleconfig.filters = FilterAttribute("site").eq("/.*/")

vtyconfig = VtyConfig()
vtyconfig.filters = FilterAttribute("site").eq("/.*/")

globalconfig = GlobalConfig()
globalconfig.filters = FilterAttribute("site").eq("/.*/")