from acex.configuration.components.base_component import ConfigComponent
from acex.configuration.components.interfaces import Interface, Svi
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
            
            elif isinstance(si, str):
                ref = ReferenceTo(pointer=f"interfaces.{si}")
                self.kwargs["source_interface"] = ref

            elif isinstance(si, Interface) or isinstance(si, Svi):
                ref = ReferenceTo(pointer=f"interfaces.{si.name}")
                self.kwargs["source_interface"] = ref

        # Normalize server_group to its name
        if "server_group" in self.kwargs:
            server_group = self.kwargs.pop("server_group")
            self.kwargs["server_group"] = server_group.name

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

            elif isinstance(si, Interface) or isinstance(si, Svi):
                ref = ReferenceTo(pointer=f"interfaces.{si.name}")
                self.kwargs["source_interface"] = ref

        # Normalize server_group to its name
        if "server_group" in self.kwargs:
            server_group = self.kwargs.pop("server_group")
            self.kwargs["server_group"] = server_group.name

class aaaServerGroup(ConfigComponent):
    type = "aaaServerGroup"
    model_cls = aaaServerGroupAttributes

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