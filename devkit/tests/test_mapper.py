import pytest
from acex_devkit.drivers.mapper import (
    Block,
    Choice,
    Dispatch,
    Flag,
    Ipv4Mask,
    Keyword,
    Line,
    Mapper,
    Mount,
    Multiline,
    Pattern,
    Pointer,
    Section,
    Vlans,
)
from acex_devkit.models.composed_configuration import (
    ComposedConfiguration,
    EthernetCsmacdInterface,
    L3IpvlanInterface,
    NetworkInstance,
    NtpServer,
    SshServer,
    StormControlAttributes,
    SubInterface,
    SystemConfig,
    aaaRadiusAttributes,
    aaaServerGroupAttributes,
    aaaTacacsAttributes,
)


class SystemSyntax(Block):
    path = "system.config"
    component = SystemConfig
    body = (
        Line("hostname {hostname}"),
        Multiline("motd_banner", "banner motd {delim}"),
    )


class VrfSyntax(Block):
    path = "network_instances"
    header = Line("vrf definition {name}")
    component = NetworkInstance
    body = (
        Line("description {description:rest}"),
        Section("address-family ipv4", footer="exit-address-family", always=True),
    )

    def includes(self, key, component):
        return key != "global"


class TacacsMemberSyntax(Block):
    path = "tacacs"
    header = Line("server name {name}")
    component = aaaTacacsAttributes
    when = {"type": "tacacs"}


class RadiusMemberSyntax(Block):
    path = "radius"
    header = Line("server name {name}")
    component = aaaRadiusAttributes
    when = {"type": "radius"}


class ServerGroupSyntax(Block):
    path = "system.aaa.server_groups"
    header = Line("aaa group server {type} {name}", type=Choice(tacacs="tacacs+", radius="radius"))
    key = "name"
    component = aaaServerGroupAttributes
    body = (TacacsMemberSyntax(), RadiusMemberSyntax())


class StormControlSyntax(Block):
    path = "storm_control"
    component = StormControlAttributes
    body = (Line("storm-control broadcast level pps {broadcast_pps:int}"),)


class InterfaceSyntax(Block):
    path = "interfaces"
    header = Line("interface {name}")
    component = Dispatch("name", {r"\.\d+$": SubInterface, r"^Vlan": L3IpvlanInterface, r"": EthernetCsmacdInterface})
    body = (
        Line("description {description:rest}"),
        Line("encapsulation dot1Q {vlan_id:int}", only=SubInterface),
        Line("switchport trunk allowed vlan {trunk_allowed_vlans:vlans}"),
        Mount("vrf forwarding {vrf}", at="network_instances.{vrf}.interfaces", default={"vrf": "global"}),
        Line("ip address {ipv4:ipv4_mask}"),
        Line("lacp rate {lacp_interval}", lacp_interval=Choice(fast="fast", slow="normal")),
        StormControlSyntax(),
        Flag("enabled", on="no shutdown", off="shutdown", default=True),
    )

    def complete(self, fields, position, context):
        return {"index": position, **fields}


class SshSyntax(Block):
    path = "system.ssh.config"
    component = SshServer
    body = (Line("ip ssh source-interface {source_interface}", source_interface=Pointer("interfaces")),)


class NtpSyntax(Block):
    path = "system.ntp.servers"
    header = Line("ntp server {address}[ {prefer}]", prefer=Keyword("prefer"))
    component = NtpServer


MAPPER = Mapper(
    [SystemSyntax(), VrfSyntax(), ServerGroupSyntax(), InterfaceSyntax(), SshSyntax(), NtpSyntax()],
    indent=" ",
    separator="!",
)

RUNNING = """\
hostname SW1
banner motd ^C
keep out
^C
!
vrf definition MGMT
 description Management
 !
 address-family ipv4
 exit-address-family
!
aaa group server tacacs+ TAC
 server name ise1
 server name ise2
!
aaa group server radius RAD
 server name rad1
!
ntp server 10.0.0.1 prefer
ntp server 10.0.0.2
!
line vty 0 4
 description not an interface
!
interface GigabitEthernet0/0
 vrf forwarding MGMT
 ip address 192.168.1.10 255.255.255.0
!
interface GigabitEthernet0/1
 description Uplink to core
 switchport trunk allowed vlan 1-3,10
 lacp rate normal
 storm-control broadcast level pps 2000
 speed 1000
!
interface GigabitEthernet0/1.20
 encapsulation dot1Q 20
 ip address 10.1.1.1 255.255.255.0
 shutdown
!
interface Vlan10
 vrf forwarding MISSING
 ip address 10.0.10.1 255.255.255.0
!
ip ssh source-interface Vlan10
"""


def test_tokens_round_trip():
    assert Vlans().parse("1-3,10") == [1, 2, 3, 10]
    assert Vlans().render([10, 3, 1, 2]) == "1-3,10"
    assert Ipv4Mask().parse("10.0.0.1 255.255.255.0") == "10.0.0.1/24"
    assert Ipv4Mask().render("10.0.0.1/24") == "10.0.0.1 255.255.255.0"
    assert Choice(slow="normal").parse("normal") == "slow"
    assert Pointer("interfaces").parse("Lo0").pointer == "interfaces.Lo0"
    assert Pointer("interfaces").render(Pointer("interfaces").parse("Gi0/1.10")) == "Gi0/1.10"


def test_pattern_optional_segment():
    pattern = Pattern("ntp server {address}[ {prefer}]", {"prefer": Keyword("prefer")})
    assert pattern.render({"address": "1.1.1.1", "prefer": True}) == "ntp server 1.1.1.1 prefer"
    assert pattern.render({"address": "1.1.1.1", "prefer": False}) == "ntp server 1.1.1.1"
    assert pattern.render({"prefer": True}) is None
    assert pattern.match("ntp server 1.1.1.1") == {"address": "1.1.1.1"}
    assert pattern.match("ntp server 1.1.1.1 burst") is None


def test_parse_lines_and_dispatch():
    config = MAPPER.parse(RUNNING).configuration

    assert config.system.config.hostname.value == "SW1"
    assert config.system.config.motd_banner.value == "keep out"
    assert config.system.ntp.servers["10.0.0.1"].prefer.value is True
    assert config.system.ntp.servers["10.0.0.2"].prefer is None

    uplink = config.interfaces["GigabitEthernet0/1"]
    assert type(uplink) is EthernetCsmacdInterface
    assert uplink.trunk_allowed_vlans.value == [1, 2, 3, 10]
    assert uplink.lacp_interval.value == "slow"
    assert uplink.enabled.value is True  # no `shutdown` line: the device default

    sub = config.interfaces["GigabitEthernet0/1.20"]
    assert type(sub) is SubInterface
    assert (sub.vlan_id.value, sub.ipv4.value, sub.enabled.value) == (20, "10.1.1.1/24", False)

    svi = config.interfaces["Vlan10"]
    assert type(svi) is L3IpvlanInterface
    assert svi.vlan_id is None  # encapsulation is only for subinterfaces


def test_parse_nesting():
    config = MAPPER.parse(RUNNING).configuration

    groups = config.system.aaa.server_groups
    assert list(groups["TAC"].tacacs) == ["ise1", "ise2"] and not groups["TAC"].radius
    assert list(groups["RAD"].radius) == ["rad1"] and not groups["RAD"].tacacs

    assert config.network_instances["MGMT"].description.value == "Management"
    assert config.interfaces["GigabitEthernet0/1"].storm_control.broadcast_pps.value == 2000
    assert config.interfaces["GigabitEthernet0/0"].storm_control is None  # sub-model created only by its lines


def test_parse_references():
    config = MAPPER.parse(RUNNING).configuration

    assert config.network_instances["MGMT"].interfaces["GigabitEthernet0/0"].pointer == "interfaces.GigabitEthernet0/0"
    assert "GigabitEthernet0/1" in config.network_instances["global"].interfaces  # no vrf line: the default
    assert "GigabitEthernet0/0" not in config.network_instances["global"].interfaces
    assert config.system.ssh.config.source_interface.pointer == "interfaces.Vlan10"


def test_unmatched_lines():
    unmatched = [u.line.strip() for u in MAPPER.parse(RUNNING).metadata.unmatched]
    assert unmatched == [
        "line vty 0 4",
        "description not an interface",  # the vty body is never read as anything else
        "speed 1000",
        "vrf forwarding MISSING",  # its collection doesn't exist
    ]


def test_render_parse_round_trip():
    config = MAPPER.parse(RUNNING).configuration
    rendered = MAPPER.render(config).payload
    assert MAPPER.render(MAPPER.parse(rendered).configuration).payload == rendered
    assert ComposedConfiguration.model_validate(config.model_dump())

    lines = rendered.splitlines()
    assert lines[lines.index("interface GigabitEthernet0/0") + 1] == " vrf forwarding MGMT"
    assert "vrf definition global" not in lines
    assert [" address-family ipv4", " exit-address-family"] == lines[lines.index("vrf definition MGMT") + 2 :][:2]
    assert lines[lines.index("aaa group server radius RAD") + 1] == " server name rad1"
    assert " storm-control broadcast level pps 2000" in lines


def test_item_fields_must_exist():
    class Typo(Block):
        path = "system.config"
        component = SystemConfig
        body = (Line("hostname {host_name}"),)

    with pytest.raises(ValueError, match="fits none"):
        Typo()


def test_header_must_match_path_kind():
    class SingletonWithHeader(Block):
        path = "system.config"
        component = SystemConfig
        header = Line("hostname {hostname}")

    with pytest.raises(ValueError, match="single object"):
        Mapper([SingletonWithHeader()])


def test_supported_components():
    assert MAPPER.supported_components() == [
        "interfaces",
        "network_instances",
        "system.aaa.server_groups",
        "system.config",
        "system.ntp.servers",
        "system.ssh.config",
    ]


def test_unmatched_lines_carry_their_block_headers():
    parents = {u.line.strip(): u.parents for u in MAPPER.parse(RUNNING).metadata.unmatched}
    assert parents["line vty 0 4"] == []
    assert parents["description not an interface"] == ["line vty 0 4"]  # an unmodelled block's own header
    assert parents["speed 1000"] == ["interface GigabitEthernet0/1"]
    assert parents["vrf forwarding MISSING"] == ["interface Vlan10"]


def test_parse_spans_tie_lines_to_tree_paths():
    spans = {".".join(s.path): (s.start, s.end) for s in MAPPER.parse(RUNNING).metadata.spans}
    assert spans["system.config"] == (1, 4)  # hostname and the whole banner
    assert spans["network_instances.MGMT"] == (6, 10)  # sections and their footer belong to the VRF
    assert spans["system.aaa.server_groups.TAC"] == (12, 14)
    assert spans["system.aaa.server_groups.TAC.tacacs.ise2"] == (14, 14)
    assert spans["interfaces.GigabitEthernet0/1"] == (29, 34)  # unparsed lines in the block still count
    assert spans["interfaces.GigabitEthernet0/1.storm_control"] == (33, 33)
    assert spans["system.ssh.config"] == (45, 45)


def test_render_spans_tie_lines_to_tree_paths():
    config = MAPPER.parse(RUNNING).configuration
    config.interfaces = {"uplink": config.interfaces["GigabitEthernet0/1"]}  # keyed like a desired tree
    result = MAPPER.render(config)
    lines = result.payload.splitlines()
    spans = {".".join(s.path): (s.start, s.end) for s in result.metadata.spans}

    start, end = spans["interfaces.uplink"]
    assert lines[start - 1] == "interface GigabitEthernet0/1" and lines[end - 1].startswith(" ")
    assert lines[end] == "!" or end == len(lines)
    start, end = spans["interfaces.uplink.storm_control"]
    assert lines[start - 1 : end] == [" storm-control broadcast level pps 2000"]
    assert spans["system.config"][0] == 1
