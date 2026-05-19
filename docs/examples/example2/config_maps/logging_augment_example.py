from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.augments.cisco import (
    CiscoLoggingTrap,
    CiscoLoggingConsole,
    CiscoLoggingSsh
)
from acex.configuration.components.system.logging import LoggingConfig, Console
#from .logging_stuff import LoggingConfig, Console

from acex.configuration.components.system.ssh import SshServer

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

logg = SetCiscoLogging()
logg.filters = FilterAttribute("hostname").eq("/.*/")# & FilterAttribute("hostname").ne("R2")
