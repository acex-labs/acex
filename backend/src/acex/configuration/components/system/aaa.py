from acex.configuration.components.base_component import ConfigComponent
from acex.configuration.components.interfaces import Interface
from acex_devkit.models.composed_configuration import (
    ReferenceTo,
    aaaGlobalAttributes,
    aaaRadiusAttributes,
    aaaServerGroupAttributes,
    aaaTacacsAttributes,
)
from acex_devkit.models.composed_configuration import aaaAccountingConfig as aaaAccountingConfigAttributes
from acex_devkit.models.composed_configuration import aaaAccountingEvents as aaaAccountingEventsAttributes
from acex_devkit.models.composed_configuration import aaaAccountingMethods as aaaAccountingMethodsAttributes
from acex_devkit.models.composed_configuration import aaaAuthenticationConfig as aaaAuthenticationConfigAttributes
from acex_devkit.models.composed_configuration import aaaAuthenticationMethods as aaaAuthenticationMethodsAttributes
from acex_devkit.models.composed_configuration import aaaAuthorizationConfig as aaaAuthorizationConfigAttributes
from acex_devkit.models.composed_configuration import aaaAuthorizationEvents as aaaAuthorizationEventsAttributes
from acex_devkit.models.composed_configuration import aaaAuthorizationMethods as aaaAuthorizationMethodsAttributes


class aaaGlobal(ConfigComponent):
    type = "aaaGlobal"
    model_cls = aaaGlobalAttributes


class aaaTacacs(ConfigComponent):
    type = "aaaTacacs"
    model_cls = aaaTacacsAttributes
    # references = {"source_interface": Interface}

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

        if "server_group" in self.kwargs:
            self.kwargs["server_group"] = self.kwargs.pop("server_group").name


class aaaRadius(ConfigComponent):
    type = "aaaRadius"
    model_cls = aaaRadiusAttributes
    # references = {"source_interface": Interface}

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

        if "server_group" in self.kwargs:
            self.kwargs["server_group"] = self.kwargs.pop("server_group").name


class aaaServerGroup(ConfigComponent):
    type = "aaaServerGroup"
    model_cls = aaaServerGroupAttributes


class aaaAuthenticationConfig(ConfigComponent):
    type = "aaaAuthenticationConfig"
    model_cls = aaaAuthenticationConfigAttributes


class aaaAuthorizationConfig(ConfigComponent):
    type = "aaaAuthorizationConfig"
    model_cls = aaaAuthorizationConfigAttributes


class aaaAccountingConfig(ConfigComponent):
    type = "aaaAccountingConfig"
    model_cls = aaaAccountingConfigAttributes


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
