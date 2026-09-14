from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.logging_server import (
    RemoteLogging,
    ConsoleLogging,
    VtyLogging,
    GlobalLogging,
    FileLogging
)

class RemoteLoggingConfig(ConfigMap):
    def compile(self, context):

        remote_server1 = RemoteLogging(
            name='logg-server.ngninfra.net',
            host='192.168.1.234',
            port=514, # default 514, does not have to be defined
            transport='udp', # default udp, does not have to be defined
            source_address='vlan2'
        )
        context.configuration.add(remote_server1)

        # Can't handle two if you don't define source_address on each one..
        # Needs to be fixed first.
        #remote_server2 = RemoteLogging(
        #    name='jani-test2',
        #    host='100.123.13.37',
        #    port=123,
        #    transport='tcp',
        #    #source_address='vlan1337'
        #)
#
        #context.configuration.add(remote_server2)

class ConsoleConfig(ConfigMap):
    def compile(self, context):

        console_line0 = ConsoleLogging(
            name='line con 0',
            line_number=0,
            logging_synchronous=True
        )
    
        context.configuration.add(console_line0)

class VtyConfig(ConfigMap):
    def __init__(self, vtylines):
        self.vtylines = vtylines

    def compile(self, context):

        vty_line = VtyLogging(
            name='line_vty',
            logging_synchronous=True
        )
        context.configuration.add(vty_line)
        #for vty_line in self.vtylines:
        #    VtyLine = VtyLogging(
        #        name='line vty {}'.format(vty_line),
        #        line_number=vty_line,
        #        logging_synchronous=True
        #    )
#
        #    context.configuration.add(VtyLine)

class GlobalConfig(ConfigMap):
    def compile(self, context):

        global_config = GlobalLogging(
            name='global_logging',
            buffer_size=8096,
        )
    
        context.configuration.add(global_config)

class FileConfig(ConfigMap):
    def compile(self, context):

        file_config = FileLogging(
            name='file_logging',
            filename='my-logs',
            rotate=3,
            max_size=8096,
            facility='info'
        )

        context.configuration.add(file_config)


remoteloggingconfig = RemoteLoggingConfig()
remoteloggingconfig_filter = FilterAttribute("hostname").eq("/.*/")
remoteloggingconfig.filters = remoteloggingconfig_filter

consoleconfig = ConsoleConfig()
consoleconfig_filter = FilterAttribute("hostname").eq("/.*/")
consoleconfig.filters = consoleconfig_filter

vtylines = [0,1,2,3]
vtyconfig = VtyConfig(vtylines)
vtyconfig_filter = FilterAttribute("hostname").eq("/.*/")
vtyconfig.filters = vtyconfig_filter

globalconfig = GlobalConfig()
globalconfig_filter = FilterAttribute("hostname").eq("/.*/")
globalconfig.filters = globalconfig_filter

fileconfig = FileConfig()
fileconfig_filter = FilterAttribute("hostname").eq("/.*/")
fileconfig.filters = fileconfig_filter