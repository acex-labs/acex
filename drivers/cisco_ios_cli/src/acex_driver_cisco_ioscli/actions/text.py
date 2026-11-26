"""What the IOS commands' outputs have in common."""

import re


class IOSText:
    """Patterns and readings shared by the commands' outputs."""

    IP = r"\d{1,3}(?:\.\d{1,3}){3}"
    MAC = r"[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}"
    CLOCK = re.compile(r"(?P<h>\d+):(?P<m>\d{2}):(?P<s>\d{2})")
    PERIOD = re.compile(r"(?:\d+[ywdhms])+")
    UNIT = re.compile(r"(?P<value>\d+)(?P<unit>[ywdhms])")
    SECONDS = {"y": 365 * 86400, "w": 7 * 86400, "d": 86400, "h": 3600, "m": 60, "s": 1}

    @classmethod
    def is_age(cls, text: str) -> bool:
        return bool(cls.CLOCK.fullmatch(text) or cls.PERIOD.fullmatch(text))

    @classmethod
    def age_seconds(cls, text: str | None) -> int | None:
        """`00:12:34`, `1d02h`, `2w3d`, `1y5w` in seconds; None for anything else, e.g. `never`."""
        if not text:
            return None
        if clock := cls.CLOCK.fullmatch(text):
            return int(clock["h"]) * 3600 + int(clock["m"]) * 60 + int(clock["s"])
        if cls.PERIOD.fullmatch(text):
            return sum(int(m["value"]) * cls.SECONDS[m["unit"]] for m in cls.UNIT.finditer(text))
        return None

    @staticmethod
    def mac(address: str) -> str:
        """`aa:bb:cc:dd:ee:ff` as IOS writes it: `aabb.ccdd.eeff`."""
        digits = address.replace(":", "")
        return ".".join(digits[i : i + 4] for i in range(0, 12, 4))
