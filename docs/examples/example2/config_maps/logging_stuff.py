from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.logging import (
    LoggingServer,
    LoggingConsole,
    LoggingConfig,
    #GlobalConfig,
    VtyLines
#    GlobalLogging,
)

#from acex.configuration.components.interfaces import Svi # We will not use interface reference here for now as source_interface can be both an IP address or an interface.

class GlobalConfig(ConfigMap):
    def compile(self, context):

        global_config = LoggingConfig(
            buffer_size=65536,
        )
    
        context.configuration.add(global_config)

class LoggingServerConfig(ConfigMap):
    def compile(self, context):

        # We will not use interface reference here for now as source_interface can be both an IP address or an interface.
        #svi2 = Svi(
        #    name="svi2",
        #    vlan_id=2,
        #    index=0
        #)
        #context.configuration.add(svi2)

        remote_server1 = LoggingServer(
            name='logg-server1.test.net',
            host='123.123.123.123',
            port=514, # default 514, does not have to be defined
            transport='udp', # default udp, does not have to be defined
            source_interface='svi2'
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

loggingserverconfig = LoggingServerConfig()
loggingserverconfig_filter = FilterAttribute("site").eq("C3241128")
loggingserverconfig.filters = loggingserverconfig_filter

consoleconfig = ConsoleConfig()
consoleconfig_filter = FilterAttribute("site").eq("C3241128")
consoleconfig.filters = consoleconfig_filter

vtyconfig = VtyConfig()
vtyconfig_filter = FilterAttribute("site").eq("C3241128")
vtyconfig.filters = vtyconfig_filter

globalconfig = GlobalConfig()
globalconfig_filter = FilterAttribute("site").eq("C3241128")
globalconfig.filters = globalconfig_filter