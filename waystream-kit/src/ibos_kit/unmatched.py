import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ibos_kit.accounting import lines_with_parents


@dataclass
class Report:
    significant: int
    unmatched: list

    @property
    def translated_share(self) -> float:
        return 1.0 if not self.significant else 1 - len(self.unmatched) / self.significant

    def kinds(self) -> list[tuple[str, int]]:
        return Counter(kind(line) for line in self.unmatched).most_common()


def kind(line) -> str:
    head = line.parents[0].split()[0] if line.parents else ""
    words = " ".join(line.line.split()[:2])
    return f"{head} > {words}" if head else words


def build(codec, raw: str) -> Report:
    significant = len(lines_with_parents(codec.normalize(raw)))
    return Report(significant, codec.parse(raw, None).metadata.unmatched)


def render(report: Report, most_common: int = 10) -> str:
    share = f"{report.translated_share:.0%} translated"
    out = [f"{len(report.unmatched)} of {report.significant} lines not translated ({share})"]
    header = None
    for line in report.unmatched:
        if line.parents != header or len(out) == 1:
            header = line.parents
            out += ["", " > ".join(p.strip() for p in header) if header else "(top level)"]
        out.append(f"  {line.line}")
    if report.unmatched:
        out += ["", "Most common:"]
        out += [f"{count:6}  {name}" for name, count in report.kinds()[:most_common]]
    return "\n".join(out)


def main(codec, argv: list[str]) -> None:
    if len(argv) != 1:
        sys.exit("usage: show_unmatched.py <file, or - for standard input>")
    raw = sys.stdin.read() if argv[0] == "-" else Path(argv[0]).read_text()
    try:
        report = build(codec, raw)
    except NotImplementedError as error:
        sys.exit(f"Not there yet: {error}")
    print(render(report))
