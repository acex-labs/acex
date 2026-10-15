from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.network_instances.network_instances import L3Vrf
from acex.configuration.components.routing.routing import StaticRouteNextHop, StaticRoute   

class ConfigVRFs(ConfigMap):
    def compile(self, context):

        prod = L3Vrf(
            name="PROD"
        )
        context.configuration.add(prod)
        guest = L3Vrf(
            name="GUEST"
        )
        context.configuration.add(guest)
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

        # Export VRFs so they can be referenced from other config maps
        self.prod = prod
        self.guest = guest
        self.vrf_test = vrf_test

vrfs = ConfigVRFs()
vrfs.filters = (FilterAttribute("role").eq("lan_csw"))