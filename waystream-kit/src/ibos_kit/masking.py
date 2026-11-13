import re
from dataclasses import dataclass, field

MASK = "<REDACTED>"


@dataclass(frozen=True)
class MaskRule:
    name: str
    pattern: re.Pattern
    replacement: str
    fact: str


RULES = (
    # Syntax known from the third-party driver (SECRET-SYNTAX-SNMP-RADIUS).
    MaskRule(
        "snmp_notify_community",
        re.compile(r"^(\s*notify\s+\S+\s+community\s+)\S+(.*)$"),
        rf"\1{MASK}\2",
        "SECRET-SYNTAX-SNMP-RADIUS",
    ),
    MaskRule(
        "snmp_community",
        re.compile(r"^(\s*community\s+)\S+(.*)$"),
        rf"\1{MASK}\2",
        "SECRET-SYNTAX-SNMP-RADIUS",
    ),
    MaskRule(
        "radius_server_secret",
        re.compile(r"^(radius server\s+\S+\s+secret\s+)\S+(.*)$"),
        rf"\1{MASK}\2",
        "SECRET-SYNTAX-SNMP-RADIUS",
    ),
    # Guesses for syntax nobody has shown us (SECRET-SYNTAX-OTHER): mask the word after the keyword, and
    # keep a numeric encryption type in front of it. They err towards masking too much.
    *(
        MaskRule(
            f"guess:{word}",
            re.compile(rf"^(.*\s{word}(?:\s+\d)?\s+)(?!{re.escape(MASK)})\S+(.*)$"),
            rf"\1{MASK}\2",
            "SECRET-SYNTAX-OTHER",
        )
        for word in ("password", "secret", "key")
    ),
)


@dataclass
class MaskResult:
    text: str
    hits: dict[str, int] = field(default_factory=dict)


def mask(text: str) -> MaskResult:
    # First matching rule wins. Hits name rules, never values.
    hits: dict[str, int] = {}
    out = []
    for line in text.splitlines():
        for rule in RULES:
            new = rule.pattern.sub(rule.replacement, line)
            if new != line:
                hits[rule.name] = hits.get(rule.name, 0) + 1
                line = new
                break
        out.append(line)
    return MaskResult(text="\n".join(out) + ("\n" if text.endswith("\n") else ""), hits=hits)


def find_unmasked(text: str) -> list[tuple[int, str]]:
    # Never returns the values.
    found = []
    for number, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            if rule.pattern.sub(rule.replacement, line) != line:
                found.append((number, rule.name))
                break
    return found
