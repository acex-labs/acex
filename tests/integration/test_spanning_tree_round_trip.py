"""
A configuration composed from spanning tree components can be written as JSON and read back.

The components are placed by the configuration engine into `stp`. What it places has to be what the model types: the
global settings, RSTP and MST are one object each, the MST instances and the Rapid PVST VLANs are collections keyed by
the name of the component. A model that types one of them the other way fails to validate what the engine composed.
"""

import pytest
from acex.configuration.components.spanning_tree import (
    SpanningTreeGlobal,
    SpanningTreeMSTP,
    SpanningTreeMstpInstance,
    SpanningTreeRapidPVST,
    SpanningTreeRSTP,
)
from acex.configuration.configuration import Configuration
from acex_devkit.models.composed_configuration import ComposedConfiguration


def composed(*components) -> ComposedConfiguration:
    configuration = Configuration("lab")
    for component in components:
        configuration.add(component)
    return configuration.as_model()


def written_and_read_back(config: ComposedConfiguration) -> ComposedConfiguration:
    return ComposedConfiguration.model_validate(config.model_dump(mode="json"))


ONE_OF_EACH = {
    "global": SpanningTreeGlobal(mode="rapid-pvst", loop_guard=True, bridge_assurance=False),
    "rstp": SpanningTreeRSTP(hello_time=2, bridge_priority=4096),
    "mstp": SpanningTreeMSTP(revision=1, max_hop=20),
    "mst instance": SpanningTreeMstpInstance(name="one", instance_id=1, vlan=[10, 20]),
    "rapid pvst": SpanningTreeRapidPVST(name="users", vlan=10, bridge_priority=8192),
}


@pytest.mark.parametrize("component", ONE_OF_EACH.values(), ids=ONE_OF_EACH.keys())
def test_a_composed_configuration_validates_after_a_json_round_trip(component):
    config = composed(component)

    read_back = written_and_read_back(config)

    assert read_back.model_dump(mode="json") == config.model_dump(mode="json")


def test_the_global_settings_are_one_object():
    config = composed(SpanningTreeGlobal(mode="rapid-pvst", loop_guard=True))

    read_back = written_and_read_back(config)

    assert read_back.stp.config.mode.get_value() == "rapid-pvst"
    assert read_back.stp.config.loop_guard.get_value() is True


def test_several_mst_instances_are_all_kept():
    config = composed(
        SpanningTreeMstpInstance(name="one", instance_id=1, vlan=[10]),
        SpanningTreeMstpInstance(name="two", instance_id=2, vlan=[20, 30]),
    )

    read_back = written_and_read_back(config)

    instances = read_back.stp.mstp.mst_instances
    assert {name: entry.instance_id.get_value() for name, entry in instances.items()} == {"one": 1, "two": 2}


def test_several_rapid_pvst_vlans_are_all_kept():
    config = composed(
        SpanningTreeRapidPVST(name="users", vlan=10, bridge_priority=8192),
        SpanningTreeRapidPVST(name="voice", vlan=20, bridge_priority=4096),
    )

    read_back = written_and_read_back(config)

    vlans = read_back.stp.rapidpvst.vlan
    assert {name: entry.bridge_priority.get_value() for name, entry in vlans.items()} == {"users": 8192, "voice": 4096}


def test_a_configuration_without_spanning_tree_components_has_empty_collections():
    read_back = written_and_read_back(composed())

    assert read_back.stp.config is None
    assert read_back.stp.mstp.mst_instances == {}
    assert read_back.stp.rapidpvst.vlan == {}
