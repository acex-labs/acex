from acex.configuration.components.base_component import ConfigComponent
from acex.configuration.components.interfaces import Interface
from acex_devkit.models.composed_configuration import (
    aaaTacacsAttributes,
    aaaRadiusAttributes,
    aaaServerGroupAttributes,
    aaaAuthenticationMethods as aaaAuthenticationMethodsAttributes,
    aaaAuthorizationMethods as aaaAuthorizationMethodsAttributes,
    aaaAuthorizationEvents as aaaAuthorizationEventsAttributes,
    aaaAccountingMethods as aaaAccountingMethodsAttributes,
    aaaAccountingEvents as aaaAccountingEventsAttributes
)

class aaaTacacs(ConfigComponent):
    type = "aaaTacacs"
    model_cls = aaaTacacsAttributes

    def pre_init(self):
        # Resolve source_interface
        if "source_interface" in self.kwargs:
            si = self.kwargs.pop("source_interface")
            if isinstance(si, type(None)):
                pass
            # If source_interface is a string, we assume it's an IP that we just reference directly
            elif isinstance(si, str):
                ref = ReferenceTo(pointer=f"interfaces.{si}")
                self.kwargs["source_interface"] = ref

            elif isinstance(si, Interface):
                ref = ReferenceTo(pointer=f"interfaces.{si.name}")
                self.kwargs["source_interface"] = ref

class aaaRadius(ConfigComponent):
    type = "aaaRadius"
    model_cls = aaaRadiusAttributes

    def pre_init(self):
        # Resolve source_interface
        if "source_interface" in self.kwargs:
            si = self.kwargs.pop("source_interface")
            if isinstance(si, type(None)):
                pass
            elif isinstance(si, str):
                ref = ReferenceTo(pointer=f"interfaces.{si}")
                self.kwargs["source_interface"] = ref

            elif isinstance(si, Interface):
                ref = ReferenceTo(pointer=f"interfaces.{si.name}")
                self.kwargs["source_interface"] = ref

class aaaServerGroup(ConfigComponent):
    type = "aaaServerGroup"
    model_cls = aaaServerGroupAttributes

    def pre_init(self):
        # Resolve tacacs
        #print('='*100)
        #print('Tacacs pre_init called')
        if "tacacs" in self.kwargs:
            tacacs = self.kwargs.pop("tacacs")
            #print('tacacs:', tacacs)
            if isinstance(tacacs, type(None)):
                print('None tacacs')
                pass

            elif isinstance(tacacs, aaaTacacs):
                #print('Single tacacs server')
                ref = ReferenceTo(pointer=f"system.aaa.tacacs.{tacacs.name}")
                self.kwargs["tacacs"] = ref

            elif isinstance(tacacs, list):
                #print('Multiple tacacs servers')
                refs = {}
                for tacacs_server in tacacs:
                    if isinstance(tacacs_server, aaaTacacs):
                        ref = ReferenceTo(pointer=f"system.aaa.tacacs.{tacacs_server.name}")
                        refs[tacacs_server.name] = ref
                        #print('ref:', ref)
                #print('refs:', refs)
                self.kwargs["tacacs"] = refs
        #print('='*100)

        if "radius" in self.kwargs:
            radius = self.kwargs.pop("radius")
            if isinstance(radius, type(None)):
                pass

            elif isinstance(radius, aaaRadius):
                ref = ReferenceTo(pointer=f"system.aaa.radius.{radius.name}")
                self.kwargs["radius"] = ref

class aaaAuthenticationMethods(ConfigComponent):
    type = "aaaAuthenticationMethods"
    model_cls = aaaAuthenticationMethodsAttributes

class aaaAuthorizationMethods(ConfigComponent):
    type = "aaaAuthorizationMethods"
    model_cls = aaaAuthorizationMethodsAttributes

class aaaAuthorizationEvents(ConfigComponent):
    type = "aaaAuthorizationEvents"
    model_cls = aaaAuthorizationEventsAttributes

class aaaAccountingMethods(ConfigComponent):
    type = "aaaAccountingMethods"
    model_cls = aaaAccountingMethodsAttributes

class aaaAccountingEvents(ConfigComponent):
    type = "aaaAccountingEvents"
    model_cls = aaaAccountingEventsAttributes