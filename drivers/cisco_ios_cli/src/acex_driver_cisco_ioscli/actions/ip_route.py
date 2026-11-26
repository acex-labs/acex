import re
from ipaddress import IPv4Address, IPv4Network

from acex_devkit.models.actions import IpRouteParams, NextHop, Route

from .text import IOSText


class IpRoute:
    """`show ip route [vrf V] [address | network mask]`.

    The whole table is one line per route, its further equal-cost paths on lines of their own:

    ```
          10.0.0.0/8 is variably subnetted, 4 subnets, 3 masks
    C        10.0.0.0/24 is directly connected, GigabitEthernet1
    O IA     10.1.0.0/24 [110/2] via 10.0.0.2, 00:12:34, GigabitEthernet1
    O E2     10.2.0.0/24 [110/20] via 10.0.0.2, 1d02h, GigabitEthernet1
                         [110/20] via 10.0.0.3, 1d02h, GigabitEthernet2
          172.16.0.0/24 is subnetted, 2 subnets
    S        172.16.1.0 [1/0] via 10.0.0.1
    ```

    Under "is subnetted" all routes have the same mask and IOS leaves it out of them. An address or a network
    is answered with the one route it uses, in detail (see `parse_entry`).
    """

    NOT_IN_TABLE = ("not in table",)
    PROTOCOLS = {
        "C": "connected",
        "L": "local",
        "S": "static",
        "O": "ospf",
        "B": "bgp",
        "D": "eigrp",
        "i": "isis",
        "R": "rip",
    }
    SUBTYPES = {
        "IA": "inter_area",
        "E1": "external_1",
        "E2": "external_2",
        "N1": "nssa_1",
        "N2": "nssa_2",
        "L1": "level_1",
        "L2": "level_2",
        "EX": "external",
    }
    #: A route of a protocol with subtypes, but none on its line.
    DEFAULT_SUBTYPES = {"ospf": "intra_area", "eigrp": "internal"}
    #: BGP doesn't mark external and internal routes, but their default distances do.
    BGP_DISTANCES = {20: "external", 200: "internal"}

    ROUTE = re.compile(
        rf"^(?P<code>[A-Za-z]+)[*+%&]*\s*(?P<subtype>IA|E1|E2|N1|N2|L1|L2|EX|ia|su)?\s+"
        rf"(?P<prefix>{IOSText.IP}(?:/\d+)?)(?P<rest>.*)$"
    )
    SUBNETTED = re.compile(rf"^\s+{IOSText.IP}/(?P<length>\d+) is (?P<variably>variably )?subnetted")
    PATH = re.compile(r"^\s*\[(?P<distance>\d+)/(?P<metric>\d+)\] via (?P<via>.*)$")
    CONNECTED = re.compile(r"^\s*is (?:directly connected|a summary), (?P<via>.*)$")

    ENTRY = re.compile(rf"^Routing entry for (?P<prefix>{IOSText.IP}/\d+)", re.MULTILINE)
    KNOWN_VIA = re.compile(r'Known via "(?P<protocol>\S+)[^"]*", distance (?P<distance>\d+), metric (?P<metric>\d+)')
    #: On the Known via line, or for BGP on the Tag line after it.
    TYPE = re.compile(r", type (?P<type>[^,\n]+)")
    DESCRIPTOR = re.compile(
        rf"^\s+\*?\s*(?:(?P<address>{IOSText.IP})|directly connected)(?:, from {IOSText.IP})?"
        r"(?:, (?P<age>\S+) ago)?(?:, via (?P<interface>\S+))?\s*$",
        re.MULTILINE,
    )
    ENTRY_TYPES = {
        "intra area": "intra_area",
        "inter area": "inter_area",
        "extern 1": "external_1",
        "extern 2": "external_2",
        "NSSA extern 1": "nssa_1",
        "NSSA extern 2": "nssa_2",
        "internal": "internal",
        "external": "external",
        "level-1": "level_1",
        "level-2": "level_2",
    }

    @staticmethod
    def command(params: IpRouteParams) -> str:
        words = ["show", "ip", "route", *(["vrf", params.vrf] if params.vrf else [])]
        if isinstance(params.prefix, IPv4Network):
            words += [str(params.prefix.network_address), str(params.prefix.netmask)]
        elif isinstance(params.prefix, IPv4Address):
            words += [str(params.prefix)]
        return " ".join(words)

    @classmethod
    def parse(cls, output: str) -> list[Route]:
        """The whole table, or, when it is a detailed entry, the one route."""
        if cls.ENTRY.search(output):
            return cls.parse_entry(output)
        return cls.parse_table(output)

    @classmethod
    def parse_table(cls, output: str) -> list[Route]:
        routes: list[Route] = []
        length: int | None = None
        for line in output.splitlines():
            if subnetted := cls.SUBNETTED.match(line):
                length = None if subnetted["variably"] else int(subnetted["length"])
            elif route := cls.ROUTE.match(line):
                routes.append(cls.route(route, length))
            elif routes and (path := cls.PATH.match(line)):
                cls.add_path(routes[-1], path)
        return routes

    @classmethod
    def route(cls, match: re.Match, length: int | None) -> Route:
        protocol = cls.PROTOCOLS.get(match["code"], "other")
        route = Route(
            prefix=cls.network(match["prefix"], length),
            protocol=protocol,
            subtype=cls.SUBTYPES.get(match["subtype"] or "") or cls.DEFAULT_SUBTYPES.get(protocol),
            next_hops=[],
        )
        rest = match["rest"]
        if connected := cls.CONNECTED.match(rest):
            route.next_hops.append(NextHop(interface=connected["via"].split(", ")[-1]))
        elif path := cls.PATH.match(rest):
            cls.add_path(route, path)
        return route

    @classmethod
    def add_path(cls, route: Route, path: re.Match) -> None:
        """A `[distance/metric] via address, age, interface` path; the route's first sets its distance."""
        if route.distance is None:
            route.distance, route.metric = int(path["distance"]), int(path["metric"])
            if route.protocol == "bgp":
                route.subtype = cls.BGP_DISTANCES.get(route.distance)
        address, *details = (part.strip() for part in path["via"].split(","))
        age = next((d for d in details if IOSText.is_age(d)), None)
        if age is not None and route.age_seconds is None:
            route.age_seconds = IOSText.age_seconds(age)
        interface = next((d for d in details if d and not IOSText.is_age(d)), None)
        route.next_hops.append(NextHop(address=address.split()[0], interface=interface))

    @staticmethod
    def network(prefix: str, length: int | None) -> IPv4Network:
        """A prefix IOS writes without its mask has the mask of the "is subnetted" line above, or its class's."""
        if "/" in prefix:
            return IPv4Network(prefix)
        if length is None:
            first = int(prefix.split(".")[0])
            length = 8 if first < 128 else 16 if first < 192 else 24
        return IPv4Network(f"{prefix}/{length}")

    @classmethod
    def parse_entry(cls, output: str) -> list[Route]:
        """```
        Routing entry for 10.1.0.0/24
          Known via "ospf 1", distance 110, metric 2, type inter area
          Routing Descriptor Blocks:
          * 10.0.0.2, from 10.0.0.2, 00:12:34 ago, via GigabitEthernet1
          * directly connected, via GigabitEthernet2
        ```"""
        entry = cls.ENTRY.search(output)
        known = cls.KNOWN_VIA.search(output)
        if entry is None or known is None:
            return []
        protocol = known["protocol"] if known["protocol"] in cls.PROTOCOLS.values() else "other"
        blocks = list(cls.DESCRIPTOR.finditer(output, entry.end()))
        age = next((b["age"] for b in blocks if b["age"]), None)
        kind = cls.TYPE.search(output, known.end())
        return [
            Route(
                prefix=entry["prefix"],
                protocol=protocol,
                subtype=cls.ENTRY_TYPES.get(kind["type"].strip() if kind else "") or cls.DEFAULT_SUBTYPES.get(protocol),
                distance=int(known["distance"]),
                metric=int(known["metric"]),
                age_seconds=IOSText.age_seconds(age),
                next_hops=[NextHop(address=b["address"], interface=b["interface"]) for b in blocks],
            )
        ]
