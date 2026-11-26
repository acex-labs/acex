import re

from acex_devkit.models.actions import MacEntry

from .text import IOSText


class MacAddressTable:
    """`show mac address-table [address M] [vlan N] [interface X]`.

    ```
    Vlan    Mac Address       Type        Ports
    ----    -----------       --------    -----
     All    0100.0ccc.cccc    STATIC      CPU
      10    0050.56a1.2b3c    DYNAMIC     Gi1/0/1
    ```
    """

    ROW = re.compile(
        rf"^\s*(?P<vlan>\d+|All)\s+(?P<mac>{IOSText.MAC})\s+(?P<type>\S+)\s+(?P<ports>\S.*?)\s*$",
        re.MULTILINE,
    )
    TYPES = {"DYNAMIC": "dynamic", "STATIC": "static"}

    @staticmethod
    def command(mac: str | None = None, vlan: int | None = None, interface: str | None = None) -> str:
        """An interface is asked for on its own, since IOS doesn't take it with a VLAN; `parse` then picks
        the VLAN."""
        words = ["show", "mac", "address-table"]
        if mac:
            words += ["address", IOSText.mac(mac)]
        if interface:
            words += ["interface", interface]
        elif vlan is not None:
            words += ["vlan", str(vlan)]
        return " ".join(words)

    @classmethod
    def parse(cls, output: str, vlan: int | None = None) -> list[MacEntry]:
        """Skips the "All" rows, the switch's own multicast addresses in every VLAN, and keeps CPU rows. A row
        with several ports is an entry for each."""
        return [
            MacEntry(
                mac=row["mac"],
                vlan=int(row["vlan"]),
                interface=port,
                type=cls.TYPES.get(row["type"].upper(), "other"),
            )
            for row in cls.ROW.finditer(output)
            if row["vlan"] != "All" and (vlan is None or int(row["vlan"]) == vlan)
            for port in row["ports"].replace(",", " ").split()
        ]
