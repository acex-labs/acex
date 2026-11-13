import re


def normalize(raw: str) -> str:
    # Written as plainly as possible, independent of any driver code.
    kept = []
    for line in raw.replace("\r\n", "\n").split("\n"):
        line = line.rstrip()
        if re.match(r"^\s*!volatile", line) or line.startswith("! version") or line == "!end":
            continue
        kept.append(line)
    while kept and kept[-1] == "":
        kept.pop()
    return "\n".join(kept) + "\n"


def interface_blocks(text: str) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        if line.startswith("interface "):
            current = line.split(" ", 1)[1]
            blocks[current] = []
        elif line.startswith(" ") and current:
            blocks[current].append(line.strip())
        else:
            current = None
    return blocks
