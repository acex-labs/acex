"""The configuration tree: the shape a patch's path walks, by the rules the differ diffs by."""

from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.config_tree import ConfigTreeNode


def node(tree: ConfigTreeNode, *names: str) -> ConfigTreeNode:
    for name in names:
        tree = next(child for child in tree.children if child.name == name)
    return tree


def test_keyed_and_listed_components_are_collections():
    tree = ComposedConfiguration.tree()

    assert node(tree, "system", "ntp", "servers").kind == "collection"
    assert node(tree, "interfaces", "subinterfaces").kind == "collection"


def test_a_model_holding_only_components_is_a_branch():
    policy = node(ComposedConfiguration.tree(), "network_instances", "inter_instance_policies", "import_export_policy")

    assert policy.kind == "branch"
    assert [(c.name, c.kind) for c in policy.children] == [
        ("export_route_target", "collection"),
        ("import_route_target", "collection"),
    ]
    assert node(policy, "export_route_target", "value").kind == "attribute"
