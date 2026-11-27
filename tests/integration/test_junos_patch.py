"""
What the Junos driver renders for a patch while it cannot yet render interfaces.

A change the renderer has no generator for is listed in `metadata.unrendered` and left out of the payload. The
worker sends only what is rendered, and refuses a payload that is empty for changes it counts as rendered.
"""

import pytest
from acex_devkit.configdiffer import ConfigDiffer
from acex_devkit.models.composed_configuration import (
    ComposedConfiguration,
    EthernetCsmacdInterface,
    System,
    SystemConfig,
)
from acex_driver_juniper_junos_cli.junos_cli import JunosCodec


def port(description: str) -> EthernetCsmacdInterface:
    return EthernetCsmacdInterface(index=0, module_index=0, name="ge-0/0/0", description=description)


def with_hostname(hostname: str, **kwargs) -> ComposedConfiguration:
    return ComposedConfiguration(system=System(config=SystemConfig(hostname=hostname)), **kwargs)


def patch(desired: ComposedConfiguration, observed: ComposedConfiguration):
    diff = ConfigDiffer().diff(desired_config=desired, observed_config=observed)
    return diff, JunosCodec().render_patch(diff, None)


@pytest.mark.parametrize(
    ("desired", "observed"),
    [
        (ComposedConfiguration(interfaces={"ge-0/0/0": port("uplink")}), ComposedConfiguration()),
        (
            ComposedConfiguration(interfaces={"ge-0/0/0": port("uplink")}),
            ComposedConfiguration(interfaces={"ge-0/0/0": port("old")}),
        ),
        (ComposedConfiguration(), ComposedConfiguration(interfaces={"ge-0/0/0": port("uplink")})),
    ],
    ids=["added", "changed", "removed"],
)
def test_an_interface_change_renders_nothing_and_is_listed_as_unrendered(desired, observed):
    diff, result = patch(desired, observed)

    assert diff.get_all_changes()
    assert result.payload == ""
    assert result.metadata.unrendered == [change.path for change in diff.get_all_changes()]
    assert all(path[0] == "interfaces" for path in result.metadata.unrendered)


def test_a_hostname_change_still_renders():
    _, result = patch(with_hostname("core-2"), with_hostname("core-1"))

    assert result.payload == "set system host-name core-2"
    assert result.metadata.unrendered == []


def test_a_diff_of_both_renders_the_hostname_and_lists_only_the_interface_as_unrendered():
    desired = with_hostname("core-2", interfaces={"ge-0/0/0": port("uplink")})

    _, result = patch(desired, with_hostname("core-1"))

    assert result.payload == "set system host-name core-2"
    assert result.metadata.unrendered == [["interfaces", "ge-0/0/0"]]
