import re
from dataclasses import dataclass, field

MASK = "<REDACTED>"


@dataclass(frozen=True)
class MaskRule:
    name: str
    pattern: re.Pattern
    replacement: str
    fact: str


def _rule(name: str, pattern: str, fact: str) -> MaskRule:
    return MaskRule(name, re.compile(pattern), rf"\1{MASK}\2", fact)


RULES = (
    # Syntax shown by the third-party driver and the command reference (SECRET-SYNTAX-SNMP-RADIUS).
    _rule("snmp_notify_community", r"^(\s*notify\s+\S+\s+community\s+)\S+(.*)$", "SECRET-SYNTAX-SNMP-RADIUS"),
    _rule("snmp_community", r"^(\s*community\s+)\S+(.*)$", "SECRET-SYNTAX-SNMP-RADIUS"),
    _rule("radius_server_secret", r"^(radius server\s+\S+\s+secret\s+)\S+(.*)$", "SECRET-SYNTAX-SNMP-RADIUS"),
    # Syntax shown by the command reference only (SECRET-SYNTAX-OTHER).
    _rule(
        "tacacs_plus_secret",
        r"^(tacacs-plus\s+(?:seq\s+\d+\s+)?server\s+\S+\s+secret\s+)\S+(.*)$",
        "SECRET-SYNTAX-OTHER",
    ),
    _rule("enable_secret", r"^(enable secret\s+(?:\d\s+)?)\S+(.*)$", "SECRET-SYNTAX-OTHER"),
    _rule("console_password", r"^(console password\s+(?:\d\s+)?)\S+(.*)$", "SECRET-SYNTAX-OTHER"),
    _rule(
        "username_password",
        r"^(username\s+\S+\s+(?:role\s+li\s+)?password\s+(?:\d\s+)?)\S+(.*)$",
        "SECRET-SYNTAX-OTHER",
    ),
    _rule("snmp_user_password", r"^(\s*snmp-user\s+\S+\s+password\s+(?:\d\s+)?)\S+(.*)$", "SECRET-SYNTAX-OTHER"),
    _rule(
        "snmp_notify_user_password",
        r"^(\s*notify\s+\S+\s+user\s+\S+\s+password\s+(?:\d\s+)?)\S+(.*)$",
        "SECRET-SYNTAX-OTHER",
    ),
    _rule("license_key", r"^(\s*license\s+\S+\s+)\S+(.*)$", "SECRET-SYNTAX-OTHER"),
    # Guesses for syntax nobody has shown us, a safety net behind the rules above: mask the word after the keyword,
    # and keep a numeric encryption type in front of it. They err towards masking too much.
    *(
        _rule(f"guess:{word}", rf"^(.*\s{word}(?:\s+\d)?\s+)(?!{re.escape(MASK)})\S+(.*)$", "SECRET-SYNTAX-OTHER")
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
