"""Which Cisco assets the CLI driver takes on."""

import pytest
from acex_devkit.models.asset import Asset
from acex_devkit.models.platform import OS, Vendor
from acex_driver_cisco_ioscli.cisco_ios_cli import CiscoIOSCLIDriver
from acex_driver_cisco_ioscli.codec import CiscoIOSCodec


def cisco_asset(os: OS) -> Asset:
    return Asset(vendor=Vendor.cisco, serial_number="FOC0001", os=os, hardware_model="C9300-24P")


@pytest.mark.parametrize("os", [OS.cisco_ios, OS.cisco_iosxe])
def test_driver_takes_ios_and_iosxe_assets(os):
    assert CiscoIOSCLIDriver().supports(cisco_asset(os))


@pytest.mark.parametrize("os", [OS.cisco_nxos, OS.cisco_iosxr])
def test_driver_leaves_other_cisco_operating_systems_alone(os):
    assert not CiscoIOSCLIDriver().supports(cisco_asset(os))


def test_platforms_are_listed_in_the_driver_capabilities():
    declared = {(p.vendor, p.os) for p in CiscoIOSCLIDriver().capabilities.platforms}
    assert declared == {(Vendor.cisco, OS.cisco_ios), (Vendor.cisco, OS.cisco_iosxe)}


IOS_ACLS = """\
ip access-list standard MGMT
 permit 10.99.0.0 0.0.0.255
 permit host 10.1.1.1
 deny   any
!
ip access-list extended EDGE
 permit tcp 10.10.0.0 0.0.255.255 any eq 22
 deny   ip any any log
!
"""


def entries(config, acl):
    return {key: entry for key, entry in config.acl.ipv4_acls[acl].acl_entries.items()}


def test_acl_entries_without_sequence_numbers_are_numbered_in_order():
    result = CiscoIOSCodec().parse(IOS_ACLS, None)

    standard = entries(result.configuration, "MGMT")
    assert list(standard) == ["10", "20", "30"]
    assert [e.sequence_id.value for e in standard.values()] == [10, 20, 30]
    assert [e.action.value for e in standard.values()] == ["permit", "permit", "deny"]
    assert str(standard["10"].source_address.value) == "10.99.0.0/24"
    assert str(standard["20"].source_address.value) == "10.1.1.1/32"
    assert standard["30"].source_address.value == "any"

    extended = entries(result.configuration, "EDGE")
    assert list(extended) == ["10", "20"]
    assert extended["10"].protocol.value == "tcp"
    assert extended["10"].destination_port.value == "22"
    assert extended["20"].action.value == "deny"
    assert extended["20"].log.value is True
    assert result.metadata.unmatched == []


def test_acl_entries_with_sequence_numbers_keep_them():
    config = "ip access-list standard MGMT\n 5 permit 10.0.0.0 0.255.255.255\n 20 deny any\n!\n"

    result = CiscoIOSCodec().parse(config, None)

    assert list(entries(result.configuration, "MGMT")) == ["5", "20"]
    assert result.metadata.unmatched == []


def test_acl_entries_after_a_numbered_one_continue_from_it():
    config = "ip access-list standard MGMT\n 15 permit 10.0.0.0 0.255.255.255\n deny any\n!\n"

    result = CiscoIOSCodec().parse(config, None)

    assert list(entries(result.configuration, "MGMT")) == ["15", "25"]


def test_acl_entries_render_with_their_sequence_numbers():
    codec = CiscoIOSCodec()
    parsed = codec.parse(IOS_ACLS, None)

    rendered = codec.render(parsed.configuration, None).payload

    assert " 10 permit 10.99.0.0 0.0.0.255" in rendered
    assert " 30 deny any" in rendered
    assert " 20 deny ip any any log" in rendered
    assert codec.parse(rendered, None).configuration.acl == parsed.configuration.acl


IOS_PORTS = """\
interface GigabitEthernet1/0/1
 switchport mode access
 spanning-tree portfast edge
!
interface GigabitEthernet1/0/2
 switchport mode access
 spanning-tree portfast
!
interface GigabitEthernet1/0/3
 switchport mode trunk
 spanning-tree portfast edge trunk
!
"""


def test_portfast_edge_reads_as_portfast_and_is_written_as_portfast():
    codec = CiscoIOSCodec()

    result = codec.parse(IOS_PORTS, None)

    ports = result.configuration.interfaces
    assert [getattr(p.stp_portfast, "value", None) for p in ports.values()] == [True, True, None]
    assert [u.line.strip() for u in result.metadata.unmatched] == ["spanning-tree portfast edge trunk"]
    assert "portfast edge" not in codec.render(result.configuration, None).payload


IOS_AAA = """\
aaa new-model
aaa authentication login default group ISE local
aaa authorization config-commands
aaa authorization console
aaa authorization exec default group ISE local
aaa accounting send stop-record authentication failure
aaa accounting update newinfo periodic 2880
aaa accounting exec default start-stop group ISE
aaa session-id common
!
"""


def test_aaa_events_are_read_and_written_and_method_lists_are_left_alone():
    codec = CiscoIOSCodec()

    result = codec.parse(IOS_AAA, None)

    aaa = result.configuration.system.aaa
    assert list(aaa.authorization.config.events) == ["config-commands", "console"]
    assert list(aaa.accounting.config.events) == [
        "send stop-record authentication failure",
        "update newinfo periodic 2880",
    ]
    assert [u.line for u in result.metadata.unmatched] == [
        "aaa authentication login default group ISE local",
        "aaa authorization exec default group ISE local",
        "aaa accounting exec default start-stop group ISE",
        "aaa session-id common",
    ]
    rendered = codec.render(result.configuration, None).payload
    assert "aaa authorization console" in rendered
    assert "aaa accounting update newinfo periodic 2880" in rendered


IOS_TRACKING = """\
ip device tracking probe auto-source override
ip device tracking probe delay 60
!
interface GigabitEthernet1/0/1
 switchport mode access
 ip device tracking maximum 10
!
interface GigabitEthernet1/0/2
 switchport mode trunk
 ip device tracking maximum 0
!
"""


def tracking(owner):
    return owner.augments["cisco_ip_device_tracking"]


def test_ip_device_tracking_is_read_globally_and_per_interface():
    result = CiscoIOSCodec().parse(IOS_TRACKING, None)

    configuration = result.configuration
    assert tracking(configuration.system.config).probe_delay.value == 60
    assert tracking(configuration.system.config).probe_auto_source_override.value is True
    assert [tracking(i).maximum.value for i in configuration.interfaces.values()] == [10, 0]
    assert result.metadata.unmatched == []


def test_ip_device_tracking_is_written_back():
    codec = CiscoIOSCodec()
    parsed = codec.parse(IOS_TRACKING, None)

    rendered = codec.render(parsed.configuration, None).payload

    assert "ip device tracking probe delay 60" in rendered
    assert "ip device tracking probe auto-source override" in rendered
    assert " ip device tracking maximum 0" in rendered
    assert codec.parse(rendered, None).metadata.unmatched == []


IOS_NUMBERED_ACLS = """\
access-list 5 permit 10.99.0.0 0.0.0.255
access-list 5 permit host 10.1.1.1
access-list 5 deny   any
access-list 101 permit tcp 10.10.0.0 0.0.255.255 any eq 22
access-list 101 deny   ip any any log
!
"""


def test_numbered_access_lists_are_read_as_acls_named_by_their_number():
    result = CiscoIOSCodec().parse(IOS_NUMBERED_ACLS, None)

    acls = result.configuration.acl.ipv4_acls
    assert list(acls) == ["5", "101"]
    standard = acls["5"].acl_entries
    assert list(standard) == ["10", "20", "30"]
    assert [e.action.value for e in standard.values()] == ["permit", "permit", "deny"]
    assert str(standard["10"].source_address.value) == "10.99.0.0/24"
    extended = acls["101"].acl_entries
    assert [e.protocol.value for e in extended.values()] == ["tcp", "ip"]
    assert extended["10"].destination_port.value == "22"
    assert extended["20"].log.value is True
    assert result.metadata.unmatched == []


def test_a_numbered_access_list_is_written_as_a_named_one_with_sequence_numbers():
    codec = CiscoIOSCodec()
    parsed = codec.parse(IOS_NUMBERED_ACLS, None)

    rendered = codec.render(parsed.configuration, None).payload

    assert "ip access-list standard 5\n 10 permit 10.99.0.0 0.0.0.255" in rendered
    assert "ip access-list extended 101\n 10 permit tcp 10.10.0.0 0.0.255.255 any eq 22" in rendered
    assert not any(line.startswith("access-list ") for line in rendered.splitlines())
    assert codec.parse(rendered, None).configuration.acl == parsed.configuration.acl


def test_remarks_in_numbered_access_lists_stay_unmatched():
    result = CiscoIOSCodec().parse("access-list 5 remark management\naccess-list 5 permit any\n", None)

    assert [u.line for u in result.metadata.unmatched] == ["access-list 5 remark management"]
