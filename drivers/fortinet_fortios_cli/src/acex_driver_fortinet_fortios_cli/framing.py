from dataclasses import dataclass

from acex_devkit.models.codec_result import Span

# FortiOS closes every `config` with `end` and every `edit` with `next`, and indents four spaces a level. The devkit
# mapper nests by a one character indent and writes no closing line, so the codec reframes what it renders and what
# it parses: a render gets the closing lines and the four space indent, a parse loses them.
OPENERS = {"config": "end", "edit": "next"}
CLOSERS = frozenset(OPENERS.values())
STEP = "    "


@dataclass
class Layout:
    """The text in the other framing, and where the lines went. Line numbers are 1-based. `numbers` maps a line
    of the mapper's text, the one without closing lines, to its line in FortiOS text, and `closers_after` lists,
    for a line of the mapper's text, the header lines whose closing lines follow it in FortiOS text, innermost
    first."""

    text: str
    numbers: dict[int, int]
    closers_after: dict[int, list[int]]

    def span(self, span: Span) -> Span:
        """A span of the mapper's text as it reads in FortiOS text, taking in the closing lines of the
        components it holds."""
        closers = sum(1 for header in self.closers_after.get(span.end, []) if header >= span.start)
        return Span(start=self.numbers[span.start], end=self.numbers[span.end] + closers, path=span.path)


def widen(line: str) -> str:
    """A line of the mapper's text with the four space indent FortiOS writes."""
    body = line.lstrip(" ")
    return STEP * (len(line) - len(body)) + body


def first_word(line: str) -> str:
    words = line.split(maxsplit=1)
    return words[0] if words else ""


def insert(text: str) -> Layout:
    """The mapper's `text` as FortiOS writes it: a closing line where each `config` and `edit` block ends, found
    from the indentation, and four spaces a level."""
    lines = text.splitlines()
    out: list[str] = []
    numbers: dict[int, int] = {}
    closers_after: dict[int, list[int]] = {}
    open_blocks: list[tuple[int, str, int]] = []

    def close(depth: int, after: int) -> None:
        while open_blocks and open_blocks[-1][0] >= depth:
            level, closer, header = open_blocks.pop()
            out.append(STEP * level + closer)
            closers_after.setdefault(after, []).append(header)

    for number, line in enumerate(lines, start=1):
        body = line.lstrip(" ")
        level = len(line) - len(body)
        if body:
            close(level, number - 1)
        out.append(widen(line))
        numbers[number] = len(out)
        if first_word(body) in OPENERS:
            open_blocks.append((level, OPENERS[first_word(body)], number))
    close(0, len(lines))
    return Layout("\n".join(out) + ("\n" if text.endswith("\n") else ""), numbers, closers_after)


def remove(text: str) -> Layout:
    """FortiOS `text` as the mapper reads it: without closing lines, one space a level."""
    kept: list[str] = []
    numbers: dict[int, int] = {}
    closers_after: dict[int, list[int]] = {}
    open_blocks: list[int] = []
    for number, line in enumerate(text.splitlines(), start=1):
        body = line.lstrip(" ")
        if body.strip() in CLOSERS:
            if open_blocks and kept:
                closers_after.setdefault(len(kept), []).append(open_blocks.pop())
            continue
        kept.append(" " * ((len(line) - len(body)) // len(STEP)) + body)
        numbers[len(kept)] = number
        if first_word(body) in OPENERS:
            open_blocks.append(len(kept))
    return Layout("\n".join(kept) + ("\n" if text.endswith("\n") else ""), numbers, closers_after)
