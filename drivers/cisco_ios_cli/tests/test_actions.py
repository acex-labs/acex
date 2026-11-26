"""Each command class against IOS-XE output, and the facade against a transport that answers from it."""

import asyncio
from ipaddress import IPv4Address, IPv4Network

import pytest
from acex_devkit.exceptions import DriverException
from acex_devkit.models.actions import (
    ArpTableParams,
    InterfaceStatusParams,
    IpRouteParams,
    LookupArpParams,
    LookupMacAddressParams,
    MacAddressTableParams,
    TracerouteParams,
)
from acex_driver_cisco_ioscli.actions import CiscoIOSActions
from acex_driver_cisco_ioscli.actions.arp import Arp
from acex_driver_cisco_ioscli.actions.interfaces import Interfaces
from acex_driver_cisco_ioscli.actions.ip_route import IpRoute
from acex_driver_cisco_ioscli.actions.mac_address_table import MacAddressTable
from acex_driver_cisco_ioscli.actions.text import IOSText
from acex_driver_cisco_ioscli.actions.traceroute import Traceroute

MAC_TABLE = """\
          Mac Address Table
-------------------------------------------

Vlan    Mac Address       Type        Ports
----    -----------       --------    -----
 All    0100.0ccc.cccc    STATIC      CPU
 All    0180.c200.0000    STATIC      CPU
   1    7018.a7aa.bb00    STATIC      Vl1
  10    0050.56a1.2b3c    DYNAMIC     Gi1/0/1
  20    0050.56a1.2b3c    DYNAMIC     Gi1/0/1
  20    0100.5e00.0001    STATIC      Gi1/0/2 Gi1/0/3
  30    aabb.cc00.0300    SECURE      Te1/1/1
Total Mac Addresses for this criterion: 7
"""

ARP = """\
Protocol  Address          Age (min)  Hardware Addr   Type   Interface
Internet  10.0.0.1                -   7018.a7aa.bb00  ARPA   Vlan10
Internet  10.0.0.2               12   0050.56a1.2b3c  ARPA   Vlan10
Internet  10.0.0.3                0   Incomplete      ARPA
"""

ROUTES = """\
Codes: L - local, C - connected, S - static, R - RIP, M - mobile, B - BGP
       D - EIGRP, EX - EIGRP external, O - OSPF, IA - OSPF inter area
       N1 - OSPF NSSA external type 1, N2 - OSPF NSSA external type 2
       E1 - OSPF external type 1, E2 - OSPF external type 2, m - OMP
       i - IS-IS, su - IS-IS summary, L1 - IS-IS level-1, L2 - IS-IS level-2
       + - replicated route, % - next hop override, p - overrides from PfR

Gateway of last resort is 10.0.0.1 to network 0.0.0.0

S*    0.0.0.0/0 [1/0] via 10.0.0.1
      10.0.0.0/8 is variably subnetted, 5 subnets, 3 masks
C        10.0.0.0/24 is directly connected, GigabitEthernet1
L        10.0.0.10/32 is directly connected, GigabitEthernet1
O IA     10.1.0.0/24 [110/2] via 10.0.0.2, 00:12:34, GigabitEthernet1
O E2     10.2.0.0/24 [110/20] via 10.0.0.2, 1d02h, GigabitEthernet1
                     [110/20] via 10.0.0.3, 1d02h, GigabitEthernet2
D EX     10.3.0.0/16
           [170/3072] via 10.0.0.4, 2w3d, GigabitEthernet1
      172.16.0.0/24 is subnetted, 2 subnets
B        172.16.1.0 [200/0] via 192.168.1.1, 2w3d
B        172.16.2.0 [20/0] via 192.0.2.1, 00:00:05
O*E2  192.168.0.0/16 [110/1] via 10.0.0.2, 00:01:00, GigabitEthernet1
"""

ROUTE_ENTRY = """\
Routing entry for 10.2.0.0/24
  Known via "ospf 1", distance 110, metric 20, type extern 2, forward metric 1
  Last update from 10.0.0.2 on GigabitEthernet1, 1d02h ago
  Routing Descriptor Blocks:
  * 10.0.0.2, from 10.255.0.1, 1d02h ago, via GigabitEthernet1
      Route metric is 20, traffic share count is 1
    10.0.0.3, from 10.255.0.1, 1d02h ago, via GigabitEthernet2
      Route metric is 20, traffic share count is 1
"""

BGP_ENTRY = """\
Routing entry for 172.16.2.0/24
  Known via "bgp 65000", distance 20, metric 0
  Tag 65001, type external
  Last update from 192.0.2.1 00:00:05 ago
  Routing Descriptor Blocks:
  * 192.0.2.1, from 192.0.2.1, 00:00:05 ago
      Route metric is 0, traffic share count is 1
      AS Hops 1
"""

CONNECTED_ENTRY = """\
Routing entry for 10.0.0.0/24
  Known via "connected", distance 0, metric 0 (connected, via interface)
  Routing Descriptor Blocks:
  * directly connected, via GigabitEthernet1
      Route metric is 0, traffic share count is 1
"""

TRACEROUTE = """\
Type escape sequence to abort.
Tracing the route to dns.google (8.8.8.8)
VRF info: (vrf in name/id, vrf out name/id)
  1 10.0.0.1 1 msec 1 msec 1 msec
  2 192.0.2.1 [MPLS: Label 16 Exp 0] 5 msec
    192.0.2.5 6 msec 5 msec
  3 * * *
  4 8.8.8.8 12 msec *  10 msec
"""

TRACEROUTE_BLOCKED = """\
Type escape sequence to abort.
Tracing the route to 203.0.113.9
  1 10.0.0.1 1 msec 1 msec 1 msec
  2 198.51.100.1 !A  *  !A
"""

INTERFACES = """\
GigabitEthernet1/0/1 is up, line protocol is up (connected)
  Hardware is Gigabit Ethernet, address is 7018.a7aa.bb01 (bia 7018.a7aa.bb01)
  Description: UPLINK-ISP-Edge-Router
  MTU 1500 bytes, BW 1000000 Kbit/sec, DLY 10 usec,
  Full-duplex, 1000Mb/s, media type is 10/100/1000BaseTX
  Input queue: 0/2000/3/0 (size/max/drops/flushes); Total output drops: 7
     12 input errors, 4 CRC, 0 frame, 0 overrun, 0 ignored
     0 output errors, 0 collisions, 1 interface resets
GigabitEthernet1/0/2 is down, line protocol is down (notconnect)
  Hardware is Gigabit Ethernet, address is 7018.a7aa.bb02 (bia 7018.a7aa.bb02)
  Auto-duplex, Auto-speed, media type is 10/100/1000BaseTX
  Input queue: 0/2000/0/0 (size/max/drops/flushes); Total output drops: 0
     0 input errors, 0 CRC, 0 frame, 0 overrun, 0 ignored
     0 output errors, 0 collisions, 0 interface resets
GigabitEthernet1/0/3 is administratively down, line protocol is down (disabled)
  Auto-duplex, Auto-speed, media type is 10/100/1000BaseTX
GigabitEthernet1/0/4 is down, line protocol is down (err-disabled)
  Auto-duplex, Auto-speed, media type is 10/100/1000BaseTX
TenGigabitEthernet1/1/1 is up, line protocol is up (connected)
  Full-duplex, 10Gb/s, link type is auto, media type is SFP-10GBase-SR
GigabitEthernet1 is up, line protocol is up
  Full Duplex, 1000Mbps, link type is auto, media type is Virtual
Vlan10 is up, line protocol is up , Autostate Enabled
  Description: users
  Input queue: 0/375/0/0 (size/max/drops/flushes); Total output drops: 0
"""


class FakeTransport:
    """Answers each command from `answers`, by its start."""

    def __init__(self, answers: dict[str, str]):
        self.answers = answers
        self.sent: list[str] = []

    async def send(self, command: str, timeout: float) -> str:
        self.sent.append(command)
        return next((output for start, output in self.answers.items() if command.startswith(start)), "")


def run(coroutine):
    return asyncio.run(coroutine)


# ------------------------------------------------------------------------------------------------- text


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("00:12:34", 754), ("1d02h", 93600), ("2w3d", 1468800), ("1y5w", 34560000), ("never", None), (None, None)],
)
def test_ages_read_as_seconds(text, seconds):
    assert IOSText.age_seconds(text) == seconds


# ------------------------------------------------------------------------------------------ MAC addresses


def test_mac_table_skips_all_rows_and_keeps_cpu_and_vlan_interfaces():
    entries = MacAddressTable.parse(MAC_TABLE)

    assert [(e.mac, e.vlan, e.interface, e.type) for e in entries] == [
        ("70:18:a7:aa:bb:00", 1, "Vl1", "static"),
        ("00:50:56:a1:2b:3c", 10, "Gi1/0/1", "dynamic"),
        ("00:50:56:a1:2b:3c", 20, "Gi1/0/1", "dynamic"),
        ("01:00:5e:00:00:01", 20, "Gi1/0/2", "static"),
        ("01:00:5e:00:00:01", 20, "Gi1/0/3", "static"),
        ("aa:bb:cc:00:03:00", 30, "Te1/1/1", "other"),
    ]


def test_mac_table_command_asks_for_an_interface_alone_and_picks_the_vlan_after():
    assert MacAddressTable.command(vlan=10, interface="Gi1/0/1") == "show mac address-table interface Gi1/0/1"
    assert MacAddressTable.command(mac="00:50:56:a1:2b:3c", vlan=20) == (
        "show mac address-table address 0050.56a1.2b3c vlan 20"
    )
    assert [e.vlan for e in MacAddressTable.parse(MAC_TABLE, vlan=20)] == [20, 20, 20]


def test_lookup_asks_once_per_vlan():
    transport = FakeTransport({"show mac address-table address 0050.56a1.2b3c vlan 20": MAC_TABLE})
    params = LookupMacAddressParams(mac="0050.56A1.2B3C", vlans=[10, 20])

    result = run(CiscoIOSActions().lookup_mac_address(transport, params))

    assert transport.sent == [
        "show mac address-table address 0050.56a1.2b3c vlan 10",
        "show mac address-table address 0050.56a1.2b3c vlan 20",
    ]
    assert result.found
    assert {e.vlan for e in result.entries} == {20}


def test_a_lookup_that_finds_nothing_is_not_found():
    result = run(
        CiscoIOSActions().lookup_mac_address(FakeTransport({}), LookupMacAddressParams(mac="aa:aa:aa:aa:aa:aa"))
    )

    assert not result.found and result.entries == []


def test_a_table_the_platform_lacks_fails_with_the_devices_words():
    transport = FakeTransport(
        {"show mac": "show mac address-table\n         ^\n% Invalid input detected at '^' marker.\n"}
    )

    with pytest.raises(DriverException, match="Invalid input detected"):
        run(CiscoIOSActions().get_mac_address_table(transport, MacAddressTableParams()))


# ------------------------------------------------------------------------------------------------- ARP


def test_arp_reads_own_addresses_as_static_and_incomplete_without_mac():
    entries = Arp.parse(ARP)

    assert [(str(e.ip), e.mac, e.interface, e.age_seconds, e.type) for e in entries] == [
        ("10.0.0.1", "70:18:a7:aa:bb:00", "Vlan10", None, "static"),
        ("10.0.0.2", "00:50:56:a1:2b:3c", "Vlan10", 720, "dynamic"),
        ("10.0.0.3", None, None, 0, "incomplete"),
    ]


def test_arp_table_in_a_vrf_on_an_interface():
    transport = FakeTransport({"show ip arp vrf MGMT Vlan10": ARP})

    result = run(CiscoIOSActions().get_arp_table(transport, ArpTableParams(vrf="MGMT", interface="Vlan10")))

    assert (result.vrf, len(result.entries)) == ("MGMT", 3)


def test_lookup_arp_finds_an_incomplete_entry():
    transport = FakeTransport({"show ip arp 10.0.0.3": ARP})

    result = run(CiscoIOSActions().lookup_arp(transport, LookupArpParams(ip="10.0.0.3")))

    assert result.found and result.entry.type == "incomplete"


def test_lookup_arp_without_an_entry_is_not_found():
    result = run(CiscoIOSActions().lookup_arp(FakeTransport({"show ip arp": ARP}), LookupArpParams(ip="10.0.0.9")))

    assert not result.found


def test_a_vrf_that_doesnt_exist_fails():
    transport = FakeTransport({"show ip arp vrf NOPE": "% IP ARP table vrf NOPE does not exist\n"})

    with pytest.raises(DriverException, match="NOPE does not exist"):
        run(CiscoIOSActions().get_arp_table(transport, ArpTableParams(vrf="NOPE")))


# ---------------------------------------------------------------------------------------------- routes


def test_the_legends_percent_sign_is_no_error():
    transport = FakeTransport({"show ip route": ROUTES.replace("       + - replicated", "       % - replicated")})

    assert len(run(CiscoIOSActions().get_ip_route(transport, IpRouteParams())).routes) == 9


def test_route_table_reads_protocols_subtypes_and_paths():
    routes = {str(r.prefix): r for r in IpRoute.parse(ROUTES)}

    assert list(routes) == [
        "0.0.0.0/0",
        "10.0.0.0/24",
        "10.0.0.10/32",
        "10.1.0.0/24",
        "10.2.0.0/24",
        "10.3.0.0/16",
        "172.16.1.0/24",
        "172.16.2.0/24",
        "192.168.0.0/16",
    ]
    default = routes["0.0.0.0/0"]
    assert (default.protocol, default.distance, default.metric) == ("static", 1, 0)
    assert [(str(h.address), h.interface) for h in default.next_hops] == [("10.0.0.1", None)]

    connected = routes["10.0.0.0/24"]
    assert (connected.protocol, connected.distance) == ("connected", None)
    assert [(h.address, h.interface) for h in connected.next_hops] == [(None, "GigabitEthernet1")]
    assert routes["10.0.0.10/32"].protocol == "local"

    assert (routes["10.1.0.0/24"].subtype, routes["10.1.0.0/24"].age_seconds) == ("inter_area", 754)
    external = routes["10.2.0.0/24"]
    assert (external.subtype, external.distance, external.metric) == ("external_2", 110, 20)
    assert [(str(h.address), h.interface) for h in external.next_hops] == [
        ("10.0.0.2", "GigabitEthernet1"),
        ("10.0.0.3", "GigabitEthernet2"),
    ]


def test_a_wrapped_route_takes_its_path_from_the_next_line():
    route = next(r for r in IpRoute.parse(ROUTES) if str(r.prefix) == "10.3.0.0/16")

    assert (route.protocol, route.subtype, route.distance, route.metric) == ("eigrp", "external", 170, 3072)
    assert [str(h.address) for h in route.next_hops] == ["10.0.0.4"]


def test_routes_under_is_subnetted_take_its_mask_and_bgp_its_type_from_distance():
    routes = {str(r.prefix): r for r in IpRoute.parse(ROUTES)}

    assert routes["172.16.1.0/24"].subtype == "internal"
    assert routes["172.16.2.0/24"].subtype == "external"
    assert routes["172.16.2.0/24"].next_hops[0].interface is None
    assert routes["192.168.0.0/16"].subtype == "external_2"


def test_a_route_entry_is_the_one_route_in_detail():
    [route] = IpRoute.parse(ROUTE_ENTRY)

    assert route.prefix == IPv4Network("10.2.0.0/24")
    assert (route.protocol, route.subtype, route.distance, route.metric, route.age_seconds) == (
        "ospf",
        "external_2",
        110,
        20,
        93600,
    )
    assert [(str(h.address), h.interface) for h in route.next_hops] == [
        ("10.0.0.2", "GigabitEthernet1"),
        ("10.0.0.3", "GigabitEthernet2"),
    ]


def test_bgp_and_connected_entries():
    [bgp] = IpRoute.parse(BGP_ENTRY)
    [connected] = IpRoute.parse(CONNECTED_ENTRY)

    assert (bgp.protocol, bgp.subtype, bgp.age_seconds) == ("bgp", "external", 5)
    assert [(str(h.address), h.interface) for h in bgp.next_hops] == [("192.0.2.1", None)]
    assert (connected.protocol, connected.distance) == ("connected", 0)
    assert [(h.address, h.interface) for h in connected.next_hops] == [(None, "GigabitEthernet1")]


def test_route_command_takes_an_address_or_a_network():
    assert IpRoute.command(IpRouteParams(prefix="10.2.0.5", vrf="MGMT")) == "show ip route vrf MGMT 10.2.0.5"
    assert IpRoute.command(IpRouteParams(prefix="10.2.0.0/24")) == "show ip route 10.2.0.0 255.255.255.0"
    assert IpRoute.command(IpRouteParams()) == "show ip route"


def test_no_route_is_an_empty_list_not_an_error():
    transport = FakeTransport({"show ip route": "% Network not in table\n"})

    result = run(CiscoIOSActions().get_ip_route(transport, IpRouteParams(prefix="203.0.113.1")))

    assert result.routes == []


# ------------------------------------------------------------------------------------------ traceroute


def test_traceroute_reads_every_probe_by_who_answered():
    result = Traceroute.parse(TRACEROUTE)

    assert result.destination == IPv4Address("8.8.8.8")
    assert result.reached
    assert [hop.ttl for hop in result.hops] == [1, 2, 3, 4]
    second = result.hops[1].probes
    assert [(str(p.address), p.rtt_ms) for p in second] == [("192.0.2.1", 5.0), ("192.0.2.5", 6.0), ("192.0.2.5", 5.0)]
    assert all(p.address is None and p.rtt_ms is None for p in result.hops[2].probes)
    assert [p.rtt_ms for p in result.hops[3].probes] == [12.0, None, 10.0]


def test_traceroute_blocked_on_the_way_is_not_reached():
    result = Traceroute.parse(TRACEROUTE_BLOCKED)

    assert not result.reached
    assert [p.unreachable for p in result.hops[-1].probes] == ["admin", None, "admin"]


def test_traceroute_command():
    params = TracerouteParams(target="8.8.8.8", vrf="INET", source="Loopback0", max_hops=10, probes=2, timeout=1)

    assert Traceroute.command(params) == (
        "traceroute vrf INET 8.8.8.8 numeric timeout 1 probe 2 ttl 1 10 source Loopback0"
    )


# ------------------------------------------------------------------------------------------ interfaces


def test_interfaces_read_status_speed_and_counters():
    interfaces = {i.name: i for i in Interfaces.parse(INTERFACES)}

    uplink = interfaces["GigabitEthernet1/0/1"]
    assert uplink.model_dump() == {
        "name": "GigabitEthernet1/0/1",
        "description": "UPLINK-ISP-Edge-Router",
        "admin_status": "up",
        "oper_status": "up",
        "speed_mbps": 1000,
        "duplex": "full",
        "input_errors": 12,
        "output_errors": 0,
        "input_discards": 3,
        "output_discards": 7,
    }
    down = interfaces["GigabitEthernet1/0/2"]
    assert (down.admin_status, down.oper_status, down.speed_mbps, down.duplex) == ("up", "down", None, None)
    assert (interfaces["GigabitEthernet1/0/3"].admin_status, interfaces["GigabitEthernet1/0/3"].oper_status) == (
        "down",
        "down",
    )
    assert interfaces["GigabitEthernet1/0/4"].oper_status == "err_disabled"
    assert interfaces["TenGigabitEthernet1/1/1"].speed_mbps == 10000
    assert (interfaces["GigabitEthernet1"].speed_mbps, interfaces["GigabitEthernet1"].duplex) == (1000, "full")
    vlan = interfaces["Vlan10"]
    assert (vlan.description, vlan.oper_status, vlan.speed_mbps, vlan.input_errors) == ("users", "up", None, None)


def test_interface_status_of_one_interface():
    transport = FakeTransport({"show interfaces Vlan10": INTERFACES[INTERFACES.index("Vlan10 is up") :]})

    result = run(CiscoIOSActions().get_interface_status(transport, InterfaceStatusParams(interface="Vlan10")))

    assert transport.sent == ["show interfaces Vlan10"]
    assert [i.name for i in result.interfaces] == ["Vlan10"]
