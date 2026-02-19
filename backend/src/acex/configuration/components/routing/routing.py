from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import (
    StaticRoute as StaticRouteAttributes,
    StaticRouteNextHop as StaticRouteNextHopAttributes,
    ReferenceFrom,
)

class Routing(ConfigComponent):
    def pre_init(self):
        if self.kwargs.get('network_instance') is None:
            self.kwargs["network_instance"] = "global"
        else:
            network_instance = self.kwargs.pop("network_instance")
            self.kwargs["network_instance"] = network_instance.name 

class StaticRoute(Routing): 
    type = "StaticRoute"
    model_cls = StaticRouteAttributes

    #def pre_init(self):
    #    if self.kwargs.get('network_instance') is None:
    #        self.kwargs["network_instance"] = "global"
    #    else:
    #        network_instance = self.kwargs.pop("network_instance")
    #        self.kwargs["network_instance"] = network_instance.name 

class StaticRouteNextHop(Routing):
    type = "StaticRouteNextHop"
    model_cls = StaticRouteNextHopAttributes

    def pre_init(self):
        if "static_route" in self.kwargs:
            static_route = self.kwargs.pop("static_route")
            self.kwargs["static_route"] = static_route.name
        if self.kwargs.get('network_instance') is None:
            self.kwargs["network_instance"] = "global"
        else:
            network_instance = self.kwargs.pop("network_instance")
            self.kwargs["network_instance"] = network_instance.name