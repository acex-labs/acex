from acex_devkit.configdiffer import ConfigDiffer
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.codec_result import UnmatchedLine
from acex_devkit.models.composed_configuration import (
    ComposedConfiguration,
    EthernetCsmacdInterface,
    L3IpvlanInterface,
    NetworkInstance,
    Ssh,
    SshServer,
    System,
    SystemConfig,
    authenticationUser,
)
from acex_devkit.models.reference import Reference
from acex_devkit.normalizer import MASK


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


def test_an_empty_desired_tree_declares_nothing():
    observed = ComposedConfiguration(system=System(config=SystemConfig(hostname="SW1")))
    diff = ConfigDiffer().diff(desired_config=ComposedConfiguration(), observed_config=observed)
    assert diff.total_desired == 0
    assert diff.compliance_percentage is None  # nothing to be compliant with
    assert diff.changed == [] and [c.path for c in diff.removed] == [["system", "config"]]


def test_compliance_counts_only_declared_components():
    desired = ComposedConfiguration(system=System(config=SystemConfig(hostname="SW1")))
    observed = ComposedConfiguration(system=System(config=SystemConfig(hostname="SW2")))
    diff = ConfigDiffer().diff(desired_config=desired, observed_config=observed)
    assert (diff.total_desired, diff.compliance_percentage) == (1, 0.0)


def test_undeclared_and_unparsed_are_reported_but_not_scored():
    desired = ComposedConfiguration(system=System(config=SystemConfig(hostname="SW1")))
    observed = config({"Gi1": 0}, source="Gi1", members=[])
    observed.system.config = SystemConfig(hostname="SW1")
    diff = ConfigDiffer().diff(desired_config=desired, observed_config=observed)
    diff.unparsed = [UnmatchedLine(line="line vty 0 4")]
    assert diff.compliance_percentage == 100.0
    assert diff.undeclared_count == len(diff.removed) > 0
    assert diff.summary()["unparsed_count"] == 1


def test_svis_match_on_vlan_and_ignore_the_derived_name():
    """Desired SVIs share index 0 and carry the integrator's name; observed ones are named by the device."""
    desired = ComposedConfiguration(
        interfaces={
            "svi10": L3IpvlanInterface(index=0, name="svi10", vlan_id=10, description="data"),
            "svi20": L3IpvlanInterface(index=0, name="svi20", vlan_id=20, description="voice"),
        }
    )
    observed = ComposedConfiguration(
        interfaces={
            "Vlan20": L3IpvlanInterface(index=0, name="Vlan20", vlan_id=20, description="voice"),
            "Vlan10": L3IpvlanInterface(index=1, name="Vlan10", vlan_id=10, description="data"),
        }
    )
    diff = ConfigDiffer().diff(desired_config=desired, observed_config=observed)
    assert (diff.added, diff.changed, diff.removed) == ([], [], [])


def test_a_masked_observed_secret_matches_any_desired_value():
    desired = ComposedConfiguration()
    desired.system.aaa.authentication.users = {"admin": authenticationUser(username="admin", password_hashed="$9$abc")}
    observed = ComposedConfiguration()
    observed.system.aaa.authentication.users = {"admin": authenticationUser(username="admin", password_hashed=MASK)}
    assert ConfigDiffer().diff(desired_config=desired, observed_config=observed).changed == []

    desired.system.aaa.authentication.users["admin"].privilege = AttributeValue(value=15)
    observed.system.aaa.authentication.users["admin"].privilege = AttributeValue(value=1)
    changed = ConfigDiffer().diff(desired_config=desired, observed_config=observed).changed
    assert [a.attribute_name for a in changed[0].changed_attributes] == ["privilege"]


def test_an_attribute_desired_leaves_unset_states_no_intent():
    desired = ComposedConfiguration(interfaces={"uplink": EthernetCsmacdInterface(index=0, module_index=0, name="x")})
    observed = ComposedConfiguration(
        interfaces={"Gi1": EthernetCsmacdInterface(index=0, module_index=0, name="Gi1", enabled=True, mtu=9000)}
    )
    assert ConfigDiffer().diff(desired_config=desired, observed_config=observed).changed == []


def test_an_entry_known_only_by_a_masked_secret_matches_a_desired_one():
    from acex_devkit.models.composed_configuration import SnmpCommunity

    desired = ComposedConfiguration()
    desired.system.snmp.communities = {"ro": SnmpCommunity(name="ro", community="s3cret")}
    observed = ComposedConfiguration()
    observed.system.snmp.communities = {MASK: SnmpCommunity(name=MASK, community=MASK)}
    diff = ConfigDiffer().diff(desired_config=desired, observed_config=observed)
    assert (diff.added, diff.changed, diff.removed) == ([], [], [])
