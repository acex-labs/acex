"""
Cross-package integration tests.

Exercises backend ConfigComponents against the devkit ComposedConfiguration
model, and confirms the driver packages import cleanly alongside backend and
devkit. Runs against local source (path-dependencies declared in this
project's own pyproject.toml), not published PyPI versions — this is the
compatibility check for "do these packages still work together" before a
release.
"""

from acex.configuration.components.network_instances import L3Vrf
from acex.configuration.components.routing import StaticRoute, StaticRouteNextHop
from acex.configuration.components.system.system import HostName
from acex.configuration.components.vlan import Vlan
from acex.configuration.configuration import Configuration


def test_backend_devkit_hostname_and_vlan():
    config = Configuration(logical_node_id="test-node")

    config.add(HostName(value="test-switch"))
    config.add(Vlan(name="vlan10", vlan_id=10))

    data = config.to_json()

    assert data["system"]["config"]["hostname"]["value"] == "test-switch"
    assert data["network_instances"]["global"]["vlans"]["vlan10"]["vlan_id"]["value"] == 10


def test_backend_devkit_static_route_with_references():
    config = Configuration(logical_node_id="test-node")

    vrf = L3Vrf(name="test")
    config.add(vrf)

    default_route = StaticRoute(
        name="default_route",
        network_instance=vrf,
        prefix="0.0.0.0/0",
    )
    config.add(default_route)

    next_hop = StaticRouteNextHop(
        name="nh1",
        index=1,
        next_hop="192.168.1.1",
        metric=10,
        static_route=default_route,
        network_instance=vrf,
    )
    config.add(next_hop)

    data = config.to_json()

    routes = data["network_instances"]["test"]["protocols"]["static_routes"]
    assert routes["default_route"]["prefix"]["value"] == "0.0.0.0/0"
    assert routes["default_route"]["next_hops"]["nh1"]["next_hop"]["value"] == "192.168.1.1"


def test_drivers_importable_alongside_backend_and_devkit():
    import acex_driver_cisco_ioscli  # noqa: F401
    import acex_driver_juniper_junos_cli  # noqa: F401
