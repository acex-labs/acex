import re

from acex_devkit.models.actions import InterfaceStatus


class Interfaces:
    """`show interfaces [X]`: a block per interface, from the line that names it.

    ```
    GigabitEthernet1/0/1 is up, line protocol is up (connected)
      Description: UPLINK
      Full-duplex, 1000Mb/s, media type is 10/100/1000BaseTX
      Input queue: 0/375/0/0 (size/max/drops/flushes); Total output drops: 0
         0 input errors, 0 CRC, 0 frame, 0 overrun, 0 ignored
         0 output errors, 0 collisions, 1 interface resets
    GigabitEthernet1/0/2 is administratively down, line protocol is down (disabled)
    ```

    Discards are the input queue's drops and the total output drops. Speed and duplex not yet negotiated
    (`Auto-speed`, `Auto-duplex`) are None.
    """

    STATUS = re.compile(
        r"^(?P<name>\S+) is (?P<admin>administratively down|up|down|deleted)[^,\n]*,"
        r" line protocol is (?P<protocol>\w+)(?P<detail>[^\n]*)$",
        re.MULTILINE,
    )
    DESCRIPTION = re.compile(r"^\s+Description: (?P<text>.*?)\s*$", re.MULTILINE)
    DUPLEX = re.compile(r"^\s+(?P<duplex>Full|Half|Auto)[- ]duplex(?P<rest>.*)$", re.MULTILINE | re.IGNORECASE)
    SPEED = re.compile(r"(?P<value>\d+)\s*(?P<unit>[MG])b(?:/s|ps)")
    INPUT_ERRORS = re.compile(r"(\d+) input errors")
    OUTPUT_ERRORS = re.compile(r"(\d+) output errors")
    INPUT_DISCARDS = re.compile(r"Input queue: \d+/\d+/(\d+)/\d+")
    OUTPUT_DISCARDS = re.compile(r"Total output drops: (\d+)")

    @staticmethod
    def command(interface: str | None = None) -> str:
        return " ".join(["show", "interfaces", *([interface] if interface else [])])

    @classmethod
    def parse(cls, output: str) -> list[InterfaceStatus]:
        starts = list(cls.STATUS.finditer(output))
        ends = [start.start() for start in starts[1:]] + [len(output)]
        return [cls.interface(start, output[start.end() : end]) for start, end in zip(starts, ends, strict=True)]

    @classmethod
    def interface(cls, status: re.Match, block: str) -> InterfaceStatus:
        description = cls.DESCRIPTION.search(block)
        duplex = cls.DUPLEX.search(block)
        speed = cls.SPEED.search(duplex["rest"]) if duplex else None
        return InterfaceStatus(
            name=status["name"],
            description=description["text"] or None if description else None,
            admin_status="down" if status["admin"] == "administratively down" else "up",
            oper_status=(
                "err_disabled" if "err-disabled" in status["detail"] else "up" if status["protocol"] == "up" else "down"
            ),
            speed_mbps=int(speed["value"]) * (1000 if speed["unit"] == "G" else 1) if speed else None,
            duplex=duplex["duplex"].lower() if duplex and duplex["duplex"].lower() != "auto" else None,
            input_errors=cls.count(cls.INPUT_ERRORS, block),
            output_errors=cls.count(cls.OUTPUT_ERRORS, block),
            input_discards=cls.count(cls.INPUT_DISCARDS, block),
            output_discards=cls.count(cls.OUTPUT_DISCARDS, block),
        )

    @staticmethod
    def count(pattern: re.Pattern, block: str) -> int | None:
        match = pattern.search(block)
        return int(match[1]) if match else None
