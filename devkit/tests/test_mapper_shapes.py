"""Block shapes beyond header-and-body: lines that carry their key, path parameters, and ranged keys."""

from types import SimpleNamespace as NS

import pytest
from acex_devkit.drivers.mapper import Block, Choice, Context, Flag, Keyword, Line, Mapper, Mount
from acex_devkit.models.composed_configuration import (
    ComposedConfiguration,
    DnsServerAttributes,
    HsrpGroup,
    L3IpvlanInterface,
    NetworkInstance,
    StaticRouteNextHop,
    SystemConfig,
    aaaServerGroupAttributes,
    aaaTacacsAttributes,
    authenticationUser,
)
from acex_devkit.models.logging import Console, VtyLine
from acex_devkit.models.platform import OS


class SystemSyntax(Block):
    path = "system.config"
    component = SystemConfig
    body = (
        Line("ip domain-name {domain_name}", until="16"),
        Line("ip domain name {domain_name}", since="16"),
    )


class UserSyntax(Block):
    path = "system.aaa.authentication.users"
    header = Line(
        "username {username}[ privilege {privilege:int}][ {password_hash_type} {password_hashed}]",
        password_hash_type=Choice({9: "secret 9", 7: "password 7"}),
    )
    component = authenticationUser


class HsrpSyntax(Block):
    path = "hsrp_groups"
    key = "group"
    component = HsrpGroup
    body = (
        Line("standby {group:int} ip {virtual_address}"),
        Line("standby {group:int} priority {priority:int}"),
        Line("standby {group:int} {preempt}", preempt=Keyword("preempt")),
    )


class InterfaceSyntax(Block):
    path = "interfaces"
    header = Line("interface {name}")
    component = L3IpvlanInterface
    body = (HsrpSyntax(),)

    def complete(self, fields, position, context):
        return {"index": position, **fields}


class StaticRouteSyntax(Block):
    path = "network_instances.{vrf:name}.protocols.static_routes.{prefix}.next_hops"
    key = "next_hop"
    implied = {"vrf": "global"}
    component = StaticRouteNextHop
    body = (Line("ip route[ vrf {vrf}] {prefix:ipv4_mask} {next_hop}[ {metric:int}]"),)


class VtySyntax(Block):
    path = "system.logging.vty.lines"
    header = Line("line vty {line_number:range}")
    component = VtyLine
    body = (Line("transport input {transport_input:rest}"),)


MAPPER = Mapper(
    [SystemSyntax(), UserSyntax(), InterfaceSyntax(), StaticRouteSyntax(), VtySyntax()], indent=" ", separator="!"
)

RUNNING = """\
ip domain name example.com
username admin privilege 15 secret 9 HASH
username ops password 7 0822455D
interface Vlan10
 standby 1 ip 10.0.10.1
 standby 1 priority 110
 standby 1 preempt
 standby 2 ip 10.0.10.2
ip route 0.0.0.0 0.0.0.0 10.0.0.1
ip route 0.0.0.0 0.0.0.0 10.0.0.2 200
ip route vrf MGMT 0.0.0.0 0.0.0.0 192.168.0.1
line vty 0 4
 transport input ssh
line vty 5 15
 transport input ssh
"""


@pytest.fixture
def parsed() -> ComposedConfiguration:
    result = MAPPER.parse(RUNNING)
    assert result.metadata.unmatched == []
    return result.configuration


def test_version_variants_follow_the_device_release(parsed):
    assert parsed.system.config.domain_name.value == "example.com"  # unknown release: every variant reads
    assert "ip domain name example.com" in MAPPER.render(parsed).payload.splitlines()  # and the newest writes

    old = Context(NS(asset=NS(type="asset", os=OS.cisco_ios, os_version="15.2(7)E3")))
    assert "ip domain-name example.com" in MAPPER.render(parsed, old).payload.splitlines()
    assert MAPPER.parse("ip domain name example.com", old).metadata.unmatched  # not how 15.2 writes it

    new = Context(NS(asset=NS(type="asset", os=OS.cisco_iosxe, os_version="17.9.4a")))
    assert "ip domain name example.com" in MAPPER.render(parsed, new).payload.splitlines()


def test_choice_maps_typed_values(parsed):
    users = parsed.system.aaa.authentication.users
    assert (users["admin"].privilege.value, users["admin"].password_hash_type.value) == (15, 9)
    assert (users["ops"].privilege, users["ops"].password_hash_type.value) == (None, 7)


def test_lines_carrying_their_key_build_one_component_each(parsed):
    groups = parsed.interfaces["Vlan10"].hsrp_groups
    assert {
        g: (h.virtual_address.value, h.priority and h.priority.value, h.preempt and h.preempt.value)
        for g, h in groups.items()
    } == {"1": ("10.0.10.1", 110, True), "2": ("10.0.10.2", None, None)}


def test_path_parameters_place_lines_and_imply_defaults(parsed):
    routes = parsed.network_instances["global"].protocols.static_routes["0.0.0.0/0"].next_hops
    assert {nh: r.metric and r.metric.value for nh, r in routes.items()} == {"10.0.0.1": None, "10.0.0.2": 200}
    # A VRF only a route names is created from the bound field.
    mgmt = parsed.network_instances["MGMT"]
    assert list(mgmt.protocols.static_routes["0.0.0.0/0"].next_hops) == ["192.168.0.1"]


def test_ranges_open_every_component_and_render_merged(parsed):
    lines = parsed.system.logging.vty.lines
    assert sorted(lines, key=int) == [str(n) for n in range(16)]
    assert {line.transport_input.value for line in lines.values()} == {"ssh"}
    rendered = MAPPER.render(parsed).payload.splitlines()
    assert "line vty 0 15" in rendered  # consecutive lines that render alike merge across headers

    lines["7"].transport_input.value = "telnet"
    split = [line for line in MAPPER.render(parsed).payload.splitlines() if line.startswith("line vty")]
    assert split == ["line vty 0 6", "line vty 7", "line vty 8 15"]


def test_render_round_trip(parsed):
    rendered = MAPPER.render(parsed).payload
    assert MAPPER.render(MAPPER.parse(rendered).configuration).payload == rendered
    lines = rendered.splitlines()
    assert "ip route vrf MGMT 0.0.0.0 0.0.0.0 192.168.0.1" in lines
    assert "ip route 0.0.0.0 0.0.0.0 10.0.0.2 200" in lines
    assert lines[lines.index("interface Vlan10") + 1 :][:4] == [
        " standby 1 ip 10.0.10.1",
        " standby 1 priority 110",
        " standby 1 preempt",
        " standby 2 ip 10.0.10.2",
    ]


def test_path_parameters_need_lines_that_carry_their_key():
    class Headed(Block):
        path = "network_instances.{vrf:name}.vlans"
        header = Line("vlan {vlan_id:int}")
        component = NetworkInstance

    with pytest.raises(ValueError, match="carry their key"):
        Headed()


class ConsoleSyntax(Block):
    path = "system.logging.console"
    header = Line("line con {line_number:int}")
    single = True
    component = Console
    body = (Flag("logging_synchronous", on="logging synchronous"),)


class TacacsMemberSyntax(Block):
    path = "tacacs"
    header = Line("server name {name}")
    component = aaaTacacsAttributes


class ServerGroupSyntax(Block):
    path = "system.aaa.server_groups"
    header = Line("aaa group server tacacs+ {name}")
    component = aaaServerGroupAttributes
    body = (TacacsMemberSyntax(),)


class TacacsServerSyntax(Block):
    path = "system.aaa.server_groups.{group}.tacacs"
    header = Line("tacacs server {name}")
    key = "name"
    shared = True
    component = aaaTacacsAttributes
    body = (Line("address ipv4 {address}"),)


SHAPES = Mapper([ServerGroupSyntax(), TacacsServerSyntax(), ConsoleSyntax()], indent=" ", separator="!")

SHAPES_RUNNING = """\
aaa group server tacacs+ A
 server name ISE1
aaa group server tacacs+ B
 server name ISE1
tacacs server ISE1
 address ipv4 10.0.0.1
tacacs server NOWHERE
 address ipv4 10.0.0.9
line con 0
 logging synchronous
"""


def test_a_single_object_exists_once_its_header_is_read():
    assert MAPPER.parse("hostname x").configuration.system.logging.console is None
    console = SHAPES.parse(SHAPES_RUNNING).configuration.system.logging.console
    assert (console.line_number.value, console.logging_synchronous.value) == (0, True)


def test_a_shared_header_writes_every_entry_with_its_key_and_renders_it_once():
    result = SHAPES.parse(SHAPES_RUNNING)
    groups = result.configuration.system.aaa.server_groups
    assert groups["A"].tacacs["ISE1"].address.value == groups["B"].tacacs["ISE1"].address.value == "10.0.0.1"
    assert [u.line.strip() for u in result.metadata.unmatched] == ["tacacs server NOWHERE", "address ipv4 10.0.0.9"]
    assert SHAPES.render(result.configuration).payload.count("tacacs server ISE1") == 1


class NameServerSyntax(Block):
    path = "system.dns.dns_servers"
    key = "address"
    component = DnsServerAttributes
    body = (Line("ip name-server {address:words}"),)


class RelayInterfaceSyntax(Block):
    path = "interfaces"
    header = Line("interface {name}")
    component = L3IpvlanInterface
    body = (
        Mount(
            "ip helper-address {server}", at="system.dhcp.relay.relay_servers.{server:address}.interfaces", creates=True
        ),
    )

    def complete(self, fields, position, context):
        return {"index": position, **fields}


SERVICES = Mapper([NameServerSyntax(), RelayInterfaceSyntax()], indent=" ")


def test_a_line_carrying_several_keys_builds_one_entry_per_key():
    servers = SERVICES.parse("ip name-server 1.1.1.1 8.8.8.8").configuration.system.dns.dns_servers
    assert sorted(servers) == ["1.1.1.1", "8.8.8.8"]


def test_every_membership_line_counts_and_creates_what_it_names():
    text = "interface Vlan10\n ip helper-address 10.0.0.50\n ip helper-address 10.0.0.51\n"
    relays = SERVICES.parse(text).configuration.system.dhcp.relay.relay_servers
    assert {key: list(relay.interfaces) for key, relay in relays.items()} == {
        "10.0.0.50": ["Vlan10"],
        "10.0.0.51": ["Vlan10"],
    }
    assert SERVICES.render(SERVICES.parse(text).configuration).payload.splitlines()[1:] == [
        " ip helper-address 10.0.0.50",
        " ip helper-address 10.0.0.51",
    ]
