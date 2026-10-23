from acex_devkit.configdiffer import ConfigDiffer
from acex_devkit.models.composed_configuration import (
    ComposedConfiguration,
    EthernetCsmacdInterface,
    NetworkInstance,
    Ssh,
    SshServer,
    System,
)
from acex_devkit.models.reference import Reference


def config(keys: dict[str, int], source: str, members: list[str]) -> ComposedConfiguration:
    """Interfaces keyed by `keys` (key -> port index), SSH sourced from `source`, VRF `MGMT` holding `members`."""
    interfaces = {key: EthernetCsmacdInterface(index=i, module_index=0, name=f"port{i}") for key, i in keys.items()}
    return ComposedConfiguration(
        interfaces=interfaces,
        system=System(ssh=Ssh(config=SshServer(source_interface=Reference(pointer=f"interfaces.{source}")))),
        network_instances={
            "global": NetworkInstance(name="global"),
            "MGMT": NetworkInstance(name="MGMT", interfaces={m: Reference(pointer=f"interfaces.{m}") for m in members}),
        },
    )


def changed(desired: ComposedConfiguration, observed: ComposedConfiguration) -> list[str]:
    diff = ConfigDiffer().diff(desired_config=desired, observed_config=observed)
    return sorted(f"{c.path[-1]}.{a.attribute_name}" for c in diff.changed for a in c.changed_attributes)


def test_references_to_the_same_target_are_equal_whatever_the_key():
    desired = config({"uplink": 0, "access": 1}, source="uplink", members=["access"])
    observed = config(
        {"GigabitEthernet1/0/1": 0, "GigabitEthernet1/0/2": 1}, "GigabitEthernet1/0/1", ["GigabitEthernet1/0/2"]
    )
    assert changed(desired, observed) == []


def test_references_to_another_target_differ():
    desired = config({"uplink": 0, "access": 1}, source="uplink", members=["access"])
    observed = config({"Gi1": 0, "Gi2": 1}, source="Gi2", members=["Gi1"])
    assert changed(desired, observed) == ["MGMT.interfaces", "config.source_interface"]


def test_keys_with_dots_resolve():
    desired = config({"Gi0/1.10": 4}, source="Gi0/1.10", members=[])
    observed = config({"sub": 4}, source="sub", members=[])
    assert changed(desired, observed) == []


def test_unresolved_references_compare_by_pointer():
    desired = config({"a": 0}, source="missing", members=[])
    observed = config({"b": 0}, source="missing", members=[])
    assert changed(desired, observed) == []
