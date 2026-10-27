"""Tokens: one typed value inside a pattern, converted between device text and model value."""

import ipaddress
import re
from typing import Any

from acex_devkit.models.reference import Reference


class Token:
    """A single word, kept as text. Subclasses narrow the regex and convert the value."""

    regex = r"\S+"

    def parse(self, text: str) -> Any:
        return text

    def render(self, value: Any) -> str | None:
        """Device text for `value`, or None when it can't be written (the line or segment is skipped)."""
        return str(value)


class Rest(Token):
    """Everything to the end of the line, e.g. a free-text description."""

    regex = r".+"


class Int(Token):
    regex = r"\d+"

    def parse(self, text: str) -> int:
        return int(text)


class Vlans(Token):
    """A VLAN list in range notation: `1-3,10` <-> [1, 2, 3, 10]."""

    regex = r"\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*"

    def parse(self, text: str) -> list[int]:
        vlans = []
        for part in text.split(","):
            start, _, end = part.partition("-")
            vlans.extend(range(int(start), int(end or start) + 1))
        return vlans

    def render(self, value: list[int]) -> str | None:
        ranges: list[list[int]] = []
        for vlan in sorted(set(value)):
            if ranges and vlan == ranges[-1][1] + 1:
                ranges[-1][1] = vlan
            else:
                ranges.append([vlan, vlan])
        return ",".join(str(a) if a == b else f"{a}-{b}" for a, b in ranges) or None


class Range(Token):
    """A run of numbers written as its first and last: `0 4` <-> [0, 1, 2, 3, 4]. One number is a run of one."""

    regex = r"\d+(?: \d+)?"

    def parse(self, text: str) -> list[int]:
        first, _, last = text.partition(" ")
        return list(range(int(first), int(last or first) + 1))

    def render(self, value: list[int]) -> str | None:
        return f"{value[0]} {value[-1]}" if len(value) > 1 else str(value[0])


class Words(Token):
    """Space-separated words: `1.1.1.1 8.8.8.8` <-> ["1.1.1.1", "8.8.8.8"]. As a block's key it stands for
    one entry per word; one entry's key renders on its own."""

    regex = r"\S+(?: \S+)*"

    def parse(self, text: str) -> list[str]:
        return text.split(" ")

    def render(self, value: Any) -> str | None:
        return " ".join(value) if isinstance(value, list) else str(value)


class Ipv4Mask(Token):
    """An IPv4 interface address as address and netmask: `10.0.0.1 255.255.255.0` <-> `10.0.0.1/24`."""

    regex = r"\S+ \S+"

    def parse(self, text: str) -> str:
        return ipaddress.IPv4Interface(text.replace(" ", "/")).with_prefixlen

    def render(self, value: str) -> str | None:
        interface = ipaddress.IPv4Interface(value)
        return f"{interface.ip} {interface.netmask}"


class Choice(Token):
    """A closed set of values, optionally spelled differently on the device than in the model:
    `Choice("active", "passive")`, `Choice(fast="fast", slow="normal")`, `Choice({7: "password 7"})`.
    Text outside the set doesn't match."""

    def __init__(self, *words: Any, **renamed: str):
        self.texts: dict[Any, str] = {}
        for word in words:
            self.texts |= word if isinstance(word, dict) else {word: str(word)}
        self.texts |= renamed
        self.values = {text: value for value, text in self.texts.items()}
        self.regex = "|".join(re.escape(text) for text in sorted(self.values, key=len, reverse=True))

    def parse(self, text: str) -> Any:
        return self.values[text]

    def render(self, value: Any) -> str | None:
        return self.texts.get(value)


class Keyword(Token):
    """A fixed word standing for a boolean, e.g. `prefer` on an NTP server line. Renders only when true."""

    def __init__(self, word: str):
        self.word = word
        self.regex = re.escape(word)

    def parse(self, text: str) -> bool:
        return True

    def render(self, value: bool) -> str | None:
        return self.word if value else None


class Pointer(Token):
    """A name standing for a reference to the component with that key in the collection at `collection`:
    `Pointer("interfaces")` reads `Loopback0` as `Reference(pointer="interfaces.Loopback0")`. The target is
    not looked up; whether it exists is the tree's concern, not the line's."""

    def __init__(self, collection: str):
        self.prefix = f"{collection}."

    def parse(self, text: str) -> Reference:
        return Reference(pointer=self.prefix + text)

    def render(self, value: Reference) -> str | None:
        return value.pointer.removeprefix(self.prefix) if value.pointer.startswith(self.prefix) else None


TOKENS: dict[str, Token] = {
    "word": Token(),
    "rest": Rest(),
    "int": Int(),
    "vlans": Vlans(),
    "ipv4_mask": Ipv4Mask(),
    "range": Range(),
    "words": Words(),
}
"""Tokens addressable by name in a pattern, `{field:name}`. Parameterised tokens are passed to `Line` instead."""
