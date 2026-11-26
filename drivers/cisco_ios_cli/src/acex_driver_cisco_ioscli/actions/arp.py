import re
from ipaddress import IPv4Address

from acex_devkit.models.actions import ArpEntry

from .text import IOSText


class Arp:
    """`show ip arp [vrf V] [address | interface]`.

    ```
    Protocol  Address          Age (min)  Hardware Addr   Type   Interface
    Internet  10.0.0.1                -   aabb.cc00.0100  ARPA   GigabitEthernet1
    Internet  10.0.0.2               12   0050.56a1.2b3c  ARPA   GigabitEthernet1
    Internet  10.0.0.3                0   Incomplete      ARPA
    ```

    An age of `-` is the device's own address or a static entry.
    """

    ROW = re.compile(
        rf"^Internet\s+(?P<ip>{IOSText.IP})\s+(?P<age>-|\d+)\s+(?P<mac>{IOSText.MAC}|Incomplete)"
        r"\s+\S+(?:[ \t]+(?P<interface>\S+))?[ \t]*$",
        re.MULTILINE,
    )

    @staticmethod
    def command(vrf: str | None = None, filter: str | None = None) -> str:
        """`filter` is an address or an interface."""
        return " ".join(["show", "ip", "arp", *(["vrf", vrf] if vrf else []), *([filter] if filter else [])])

    @classmethod
    def parse(cls, output: str) -> list[ArpEntry]:
        return [cls.entry(row) for row in cls.ROW.finditer(output)]

    @classmethod
    def find(cls, output: str, ip: IPv4Address) -> ArpEntry | None:
        return next((entry for entry in cls.parse(output) if entry.ip == ip), None)

    @staticmethod
    def entry(row: re.Match) -> ArpEntry:
        incomplete = row["mac"] == "Incomplete"
        own = row["age"] == "-"
        return ArpEntry(
            ip=row["ip"],
            mac=None if incomplete else row["mac"],
            interface=row["interface"],
            age_seconds=None if own else int(row["age"]) * 60,
            type="incomplete" if incomplete else "static" if own else "dynamic",
        )
