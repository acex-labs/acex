from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import ReferenceTo, ReferenceFrom
from acex_devkit.models.logging import (
    LoggingConfig as LoggingConfigAttributes,
    Console as ConsoleAttributes,
    RemoteServer as RemoteServerAttributes,
    LoggingEvent as LoggingEventAttributes,
    VtyLine as VtyLineAttributes,
    FileLogging as FileLoggingAttributes,
)
from acex_devkit.models.acl_model import (
    Ipv4AclAttributes,
    Ipv6AclAttributes,
)

class LoggingConfig(ConfigComponent):
    type= 'logging_config'
    model_cls = LoggingConfigAttributes

class Console(ConfigComponent):
    type = 'console'
    model_cls = ConsoleAttributes

class VtyLine(ConfigComponent):
    type = 'vty_line'
    model_cls = VtyLineAttributes

    def pre_init(self):
        if self.kwargs.get("ipv4acl") is not None:
            acl = self.kwargs.pop("ipv4acl")
            print('='*100)
            print('ipv4 acl')
            print(acl)
            print(acl.name)
            print(type(acl))
            print('='*100)
            if isinstance(acl, type(None)):
                print('acl is None')
                pass
            elif isinstance(acl, str):
                print('acl is a string')
                self.kwargs["ipv4acl"] = ReferenceTo(pointer=f"acl.ipv4_acls.{acl}")

            elif isinstance(acl, Ipv4AclAttributes):
                print('acl is an Ipv4AclAttributes')
                self.kwargs["ipv4acl"] = ReferenceTo(pointer=f"acl.ipv4_acls.{acl.name}")
            else:
                print('acl is of unknown type')
            
        if self.kwargs.get("ipv6acl") is not None:
            acl = self.kwargs.pop("ipv6acl")
            self.kwargs["ipv6acl"] = ReferenceFrom(pointer=f"acl.ipv6_acls.{acl.name}")

class RemoteServer(ConfigComponent):
    type = 'remote_server'
    model_cls = RemoteServerAttributes

class LoggingEvent(ConfigComponent):
    type = 'logging_event'
    model_cls = LoggingEventAttributes

class FileLogging(ConfigComponent):
    type = 'file_logging'
    #model_cls = FileConfigAttributes
    model_cls = FileLoggingAttributes