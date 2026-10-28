"""Patches: a diff scoped to a path, and rendered as the lines that take the device from observed to desired.
Added and changed components come from the desired render, removed ones are negated from the observed one."""

import pytest
from acex_devkit.configdiffer import ConfigDiffer
from acex_devkit.drivers.mapper import Block, Flag, Keyword, Line, Mapper
from acex_devkit.exceptions import DriverException
from acex_devkit.models.composed_configuration import EthernetCsmacdInterface, NtpServer, SystemConfig


class SystemSyntax(Block):
    path = "system.config"
    component = SystemConfig
    body = (Line("hostname {hostname}"), Line("snmp-server location {location:rest}"))


class InterfaceSyntax(Block):
    path = "interfaces"
    header = Line("interface {name}")
    component = EthernetCsmacdInterface
    body = (
        Line("description {description:rest}"),
        Flag("enabled", on="no shutdown", off="shutdown", default=True),
    )

    def complete(self, fields, position, context):
        # Identity is the index: the port number, so Gi2 and Gi9 are told apart whatever their order.
        return {"index": int(fields["name"][2:]), **fields}


class NtpSyntax(Block):
    path = "system.ntp.servers"
    header = Line("ntp server {address}[ {prefer}]", prefer=Keyword("prefer"))
    component = NtpServer


MAPPER = Mapper([SystemSyntax(), InterfaceSyntax(), NtpSyntax()], indent=" ", separator="!")

OBSERVED = """\
hostname sw1
snmp-server location Row A
!
interface Gi1
 description uplink
 no shutdown
!
interface Gi9
 description stale
 no shutdown
!
ntp server 10.0.0.1
ntp server 10.0.0.9
"""

DESIRED = """\
hostname sw1-new
snmp-server location Row A
!
interface Gi1
 description core uplink
 no shutdown
!
interface Gi2
 description access
 no shutdown
!
ntp server 10.0.0.1 prefer
ntp server 10.0.0.2
"""


def diff():
    return ConfigDiffer().diff(
        desired_config=MAPPER.parse(DESIRED).configuration, observed_config=MAPPER.parse(OBSERVED).configuration
    )


def patch(path: str = "", prune: bool = False) -> list[str]:
    return MAPPER.render_patch(diff().scoped(path, prune)).splitlines()


def test_adds_and_changes_without_prune_leave_undeclared_config():
    assert patch() == [
        "hostname sw1-new",
        "interface Gi1",
        " description core uplink",
        "interface Gi2",
        " description access",
        " no shutdown",
        "ntp server 10.0.0.1 prefer",
        "ntp server 10.0.0.2",
    ]


def test_prune_removes_undeclared_first_a_headed_block_by_its_header():
    assert patch(prune=True)[:2] == ["no interface Gi9", "no ntp server 10.0.0.9"]


def test_a_path_reaches_only_what_is_below_it():
    assert patch("system.ntp.servers", prune=True) == [
        "no ntp server 10.0.0.9",
        "ntp server 10.0.0.1 prefer",
        "ntp server 10.0.0.2",
    ]


def test_a_path_through_a_key_holding_dots_reaches_that_entry_alone():
    assert patch("system.ntp.servers.10.0.0.2") == ["ntp server 10.0.0.2"]


def test_a_path_ending_at_an_attribute_writes_its_line_alone():
    assert patch("interfaces.Gi1.description") == ["interface Gi1", " description core uplink"]
    assert patch("interfaces.Gi9.description", prune=True) == ["interface Gi9", " no description stale"]


def test_a_path_matches_whole_keys_only():
    assert diff().scoped("interfaces.Gi", prune=True).is_empty()


def test_in_sync_renders_nothing():
    assert MAPPER.render_patch(diff().scoped("system.config.location")) == ""


def test_a_diff_without_its_trees_cannot_be_rendered():
    with pytest.raises(DriverException):
        MAPPER.render_patch(diff().model_copy(update={"desired": None, "observed": None}))
