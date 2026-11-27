"""Tests for the topology resource via respx mocks."""

from __future__ import annotations

import pytest
import respx
from acex_client.auth import NullAuthProvider
from acex_client.http import RestClient
from acex_client.resources.topology import Topology
from acex_devkit.models.topology import TopologyPosition
from httpx import Response


@pytest.fixture
def topology():
    rest = RestClient("http://test/api/v1", NullAuthProvider(), timeout=5.0)
    try:
        yield Topology(rest)
    finally:
        rest.close()


@respx.mock
def test_graph_asks_for_each_layer_and_the_scope(topology):
    route = respx.get("http://test/api/v1/topology").mock(
        return_value=Response(
            200,
            json={
                "layers": ["lldp"],
                "nodes": [
                    {"id": "node:1", "kind": "node_instance", "label": "R1", "node_instance_id": 1, "in_scope": True},
                    {"id": "unmanaged:ap1", "kind": "unmanaged", "label": "ap1", "in_scope": True},
                ],
                "links": [
                    {
                        "id": "lldp|node:1#Gi0/1|unmanaged:ap1#eth0",
                        "layer": "lldp",
                        "a": {"node": "node:1", "interface": "Gi0/1"},
                        "b": {"node": "unmanaged:ap1", "interface": "eth0"},
                        "attributes": {"protocol": "lldp"},
                    }
                ],
            },
        )
    )

    graph = topology.graph(layers=["lldp"], region=["north", "south"], site="sto")

    params = route.calls.last.request.url.params
    assert params.get_list("layers") == ["lldp"]
    assert params.get_list("region") == ["north", "south"]
    assert params["site"] == "sto"
    assert [node.label for node in graph.nodes] == ["R1", "ap1"]
    assert graph.links[0].b.node == "unmanaged:ap1"


@respx.mock
def test_layers(topology):
    respx.get("http://test/api/v1/topology/layers").mock(
        return_value=Response(200, json=[{"key": "lldp", "label": "LLDP/CDP", "description": ""}])
    )

    assert [layer.key for layer in topology.layers()] == ["lldp"]


@respx.mock
def test_save_positions_sends_them_as_the_body(topology):
    row = {"container": "site:sto", "item": "node:1", "x": 1, "y": 2, "updated_by": "a"}
    route = respx.put("http://test/api/v1/topology/positions").mock(return_value=Response(200, json=[row]))

    saved = topology.save_positions(payload=[TopologyPosition(container="site:sto", item="node:1", x=1, y=2)])

    assert route.calls.last.request.content == b'[{"container":"site:sto","item":"node:1","x":1.0,"y":2.0}]'
    assert saved[0].updated_by == "a"


@respx.mock
def test_reset_positions_names_the_containers(topology):
    route = respx.delete("http://test/api/v1/topology/positions").mock(return_value=Response(204))

    topology.reset_positions(container=["site:sto", "site-boxes"])

    assert route.calls.last.request.url.params.get_list("container") == ["site:sto", "site-boxes"]
