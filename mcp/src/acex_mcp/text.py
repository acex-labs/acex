"""Shaping config text so it is useful to a model without flooding its context."""

from dataclasses import dataclass

_ELLIPSIS = "..."


@dataclass
class ConfigText:
    text: str
    total_lines: int
    returned_lines: int
    truncated: bool
    section: str | None = None
    matched: bool = True


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def filter_section(text: str, needle: str) -> tuple[str, bool]:
    """Keep only config blocks matching `needle` (case-insensitive substring).

    Device configs are indentation-structured, so a bare grep loses the context
    that makes a hit meaningful — "switchport access vlan 100" is useless
    without the "interface ..." line above it. For every matching line this
    keeps its enclosing block headers and its own indented children.

    Returns the filtered text and whether anything matched at all.
    """
    lines = text.splitlines()
    target = needle.lower()
    keep: set[int] = set()

    for i, line in enumerate(lines):
        if target not in line.lower():
            continue
        keep.add(i)

        # Enclosing block headers: walk back, taking each line that is less
        # indented than the shallowest one taken so far.
        depth = _indent(line)
        for j in range(i - 1, -1, -1):
            if not lines[j].strip():
                continue
            if _indent(lines[j]) < depth:
                keep.add(j)
                depth = _indent(lines[j])
                if depth == 0:
                    break

        # Children: following lines indented deeper than the match.
        base = _indent(line)
        for j in range(i + 1, len(lines)):
            if not lines[j].strip():
                continue
            if _indent(lines[j]) <= base:
                break
            keep.add(j)

    if not keep:
        return "", False

    out: list[str] = []
    previous = None
    for i in sorted(keep):
        if previous is not None and i > previous + 1:
            out.append(_ELLIPSIS)
        out.append(lines[i])
        previous = i
    return "\n".join(out), True


def prepare(text: str, *, section: str | None, max_chars: int) -> ConfigText:
    """Apply an optional section filter, then cap the result at `max_chars`."""
    total_lines = len(text.splitlines())
    matched = True

    if section:
        text, matched = filter_section(text, section)
        if not matched:
            return ConfigText(
                text="",
                total_lines=total_lines,
                returned_lines=0,
                truncated=False,
                section=section,
                matched=False,
            )

    truncated = len(text) > max_chars
    if truncated:
        # Cut on a line boundary so the model never sees half a command.
        text = text[:max_chars].rsplit("\n", 1)[0]
        hint = "narrow it with the `section` argument" if not section else "use a more specific `section` argument"
        text += f"\n\n[truncated — {hint}; do not ask for the rest of this config in one piece]"

    return ConfigText(
        text=text,
        total_lines=total_lines,
        returned_lines=len(text.splitlines()),
        truncated=truncated,
        section=section,
        matched=matched,
    )
