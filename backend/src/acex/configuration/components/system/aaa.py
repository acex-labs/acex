from acex.configuration.components.base_component import ConfigComponent
from acex.configuration.components.interfaces import Interface, Svi
from acex_devkit.models.composed_configuration import (
    aaaTacacsAttributes,
    aaaRadiusAttributes,
    aaaServerGroupAttributes,
    aaaGlobalAttributes,
    aaaAuthenticationMethods as aaaAuthenticationMethodsAttributes,
    aaaAuthorizationMethods as aaaAuthorizationMethodsAttributes,
    aaaAuthorizationEvents as aaaAuthorizationEventsAttributes,
    aaaAccountingMethods as aaaAccountingMethodsAttributes,
    aaaAccountingEvents as aaaAccountingEventsAttributes
)

class aaaGlobal(ConfigComponent):
    type = "aaaGlobal"
    model_cls = aaaGlobalAttributes

class aaaTacacs(ConfigComponent):
    type = "aaaTacacs"
    model_cls = aaaTacacsAttributes
    references = {"source_interface": Interface}

    def pre_init(self):
        if "server_group" in self.kwargs:
            self.kwargs["server_group"] = self.kwargs.pop("server_group").name

class aaaRadius(ConfigComponent):
    type = "aaaRadius"
    model_cls = aaaRadiusAttributes
    references = {"source_interface": Interface}

    def pre_init(self):
        if "server_group" in self.kwargs:
            self.kwargs["server_group"] = self.kwargs.pop("server_group").name

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