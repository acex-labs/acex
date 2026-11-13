import re

MODELLED = (
    re.compile(r"^hostname \S+$"),
    re.compile(r"^interface \S+$"),
    re.compile(r"^description .+$"),
    re.compile(r"^no shutdown$"),
    re.compile(r"^ip address \S+ \S+$"),
)


def lines_with_parents(text: str) -> list[tuple[str, tuple[str, ...]]]:
    out, header = [], None
    for line in text.replace("\r\n", "\n").splitlines():
        if not line.strip() or line.lstrip().startswith("!"):
            continue
        if line.startswith(" "):
            out.append((line, (header,) if header else ()))
        else:
            header = line.strip()
            out.append((line, ()))
    return out


def is_modelled(line: str) -> bool:
    return any(pattern.match(line.strip()) for pattern in MODELLED)


def expected_unmatched(text: str) -> list[tuple[str, tuple[str, ...]]]:
    # For a first parser that models only hostname, interface, description, shutdown and address.
    return [(line, parents) for line, parents in lines_with_parents(text) if not is_modelled(line)]


def unaccounted(text: str, unmatched_lines: list[str]) -> list[str]:
    reported = {line.strip() for line in unmatched_lines}
    return [line for line, _ in lines_with_parents(text) if not is_modelled(line) and line.strip() not in reported]
