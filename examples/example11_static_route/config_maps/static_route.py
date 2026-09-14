from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.routing import StaticRoute, StaticRouteNextHop
from acex.configuration.components.network_instances import L3Vrf

class SetStaticRoute(ConfigMap):
    def compile(self, context):
        vrf_test = L3Vrf(name="test")
        context.configuration.add(vrf_test)

        default_route = StaticRoute(
            name="default_route",
            network_instance=vrf_test,
            prefix="0.0.0.0/0",
            #next_hops=next_hops,
        )

        context.configuration.add(default_route)

        next_hop1 = StaticRouteNextHop(
            name="nh1",
            index=1,
            next_hop="192.168.1.1",
            metric=10,
            static_route=default_route,
            network_instance=vrf_test,
        )

        context.configuration.add(next_hop1)

static_route = SetStaticRoute()
static_route.filters = FilterAttribute("site").eq("auto_lab")
