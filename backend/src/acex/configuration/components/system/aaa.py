from acex.configuration.components.base_component import ConfigComponent
from acex.models.composed_configuration import ReferenceTo
from acex.configuration.components.interfaces import Interface
from acex.models.composed_configuration import (
    aaaTacacsAttributes,
    aaaRadiusAttributes,
    aaaServerGroupAttributes,
    aaaAuthenticationMethods as aaaAuthenticationMethodsAttributes,
    aaaAuthorizationMethods as aaaAuthorizationMethodsAttributes,
    aaaAccountingMethods as aaaAccountingMethodsAttributes
)

class aaaTacacs(ConfigComponent):
    type = "aaaTacacs"
    model_cls = aaaTacacsAttributes

    #def pre_init(self):
    #    # Resolve source_interface
    #    if "source_interface" in self.kwargs:
    #        si = self.kwargs.pop("source_interface")
    #        if isinstance(si, type(None)):
    #            pass
    #        elif isinstance(si, str):
    #            ref = ReferenceTo(pointer=f"interfaces.{si}")
    #            self.kwargs["source_interface"] = ref
#
    #        elif isinstance(si, Interface):
    #            ref = ReferenceTo(pointer=f"interfaces.{si.name}")
    #            self.kwargs["source_interface"] = ref

class aaaRadius(ConfigComponent):
    type = "aaaRadius"
    model_cls = aaaRadiusAttributes

    #def pre_init(self):
    #    # Resolve source_interface
    #    if "source_interface" in self.kwargs:
    #        si = self.kwargs.pop("source_interface")
    #        if isinstance(si, type(None)):
    #            pass
    #        elif isinstance(si, str):
    #            ref = ReferenceTo(pointer=f"interfaces.{si}")
    #            self.kwargs["source_interface"] = ref
#
    #        elif isinstance(si, Interface):
    #            ref = ReferenceTo(pointer=f"interfaces.{si.name}")
    #            self.kwargs["source_interface"] = ref

class aaaServerGroup(ConfigComponent):
    type = "aaaServerGroup"
    model_cls = aaaServerGroupAttributes

    def pre_init(self):
        # Resolve tacacs
        if "tacacs" in self.kwargs:
            tacacs = self.kwargs.pop("tacacs")
            if isinstance(tacacs, type(None)):
                pass

            elif isinstance(tacacs, aaaTacacs):
                ref = ReferenceTo(pointer=f"system.aaa.tacacs.{tacacs.name}")
                self.kwargs["tacacs"] = ref
                
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

class aaaAccountingMethods(ConfigComponent):
    type = "aaaAccountingMethods"
    model_cls = aaaAccountingMethodsAttributes