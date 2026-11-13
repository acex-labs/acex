import tomllib
from dataclasses import dataclass, field
from functools import cache

from ibos_kit.paths import REGISTER

LEVELS = ("VERIFIED", "INFERRED", "UNKNOWN")
BASES = ("manufacturer-doc", "third-party-driver", "third-party-report", "real-device", "none")
VERIFYING_BASES = {"manufacturer-doc", "third-party-driver", "real-device"}


@dataclass(frozen=True)
class Source:
    id: str
    kind: str
    title: str
    url: str
    read: str
    covers: str


@dataclass(frozen=True)
class Fact:
    id: str
    topic: str
    level: str
    basis: str
    sources: tuple[str, ...]
    statement: str
    reasoning: str = ""
    verify: str = ""
    assumed: bool = False

    @property
    def label(self) -> str:
        return f"{self.level} ({self.basis})" if self.level == "VERIFIED" else self.level


@dataclass(frozen=True)
class Register:
    sources: dict[str, Source] = field(default_factory=dict)
    facts: dict[str, Fact] = field(default_factory=dict)

    def problems(self) -> list[str]:
        found = []
        for fact in self.facts.values():
            if fact.level not in LEVELS:
                found.append(f"{fact.id}: level {fact.level!r} is not one of {LEVELS}")
            if fact.basis not in BASES:
                found.append(f"{fact.id}: basis {fact.basis!r} is not one of {BASES}")
            if fact.level == "VERIFIED" and fact.basis not in VERIFYING_BASES:
                found.append(f"{fact.id}: VERIFIED needs one of {sorted(VERIFYING_BASES)}, not {fact.basis}")
            if fact.level == "VERIFIED" and not fact.sources:
                found.append(f"{fact.id}: VERIFIED without sources")
            if fact.level == "UNKNOWN" and (fact.basis != "none" or fact.sources or not fact.verify):
                found.append(f"{fact.id}: UNKNOWN has basis none, no sources and says how to verify")
            if fact.level == "INFERRED" and not fact.reasoning and fact.basis != "manufacturer-doc":
                found.append(f"{fact.id}: INFERRED needs reasoning")
            if fact.level == "INFERRED" and not fact.verify and not fact.reasoning:
                found.append(f"{fact.id}: INFERRED needs reasoning or a way to verify")
            for ref in fact.sources:
                source_id = ref.split()[0]
                source = self.sources.get(source_id)
                if source is None:
                    found.append(f"{fact.id}: unknown source {source_id}")
                elif fact.level == "VERIFIED" and source.kind == "third-party-report":
                    found.append(f"{fact.id}: a third-party report cannot verify")
                elif fact.basis not in ("none",) and fact.level == "VERIFIED" and source.kind not in VERIFYING_BASES:
                    found.append(f"{fact.id}: source {source_id} cannot verify")
        return found


@cache
def load(path=REGISTER) -> Register:
    data = tomllib.loads(path.read_text())
    sources = {s["id"]: Source(**s) for s in data["source"]}
    facts = {f["id"]: Fact(**{**f, "sources": tuple(f.get("sources", ()))}) for f in data["fact"]}
    return Register(sources=sources, facts=facts)


def render_matrix(register: Register | None = None) -> str:
    register = register or load()
    out = [
        "# Evidence matrix",
        "",
        "Generated from `evidence/register.toml` by `python -m ibos_kit.evidence`. Edit the register, not this file.",
        "",
        "## Sources",
        "",
        "| Id | Kind | Source | Read |",
        "|---|---|---|---|",
    ]
    for s in register.sources.values():
        title = f"[{s.title}]({s.url})" if s.url else s.title
        out.append(f"| {s.id} | {s.kind} | {title} | {s.read} |")
    for level in LEVELS:
        facts = [f for f in register.facts.values() if f.level == level]
        out += ["", f"## {level} ({len(facts)})", ""]
        if level == "VERIFIED":
            out += ["| Id | Basis | Sources | Statement |", "|---|---|---|---|"]
            out += [f"| {f.id} | {f.basis} | {'; '.join(f.sources)} | {f.statement} |" for f in facts]
        elif level == "INFERRED":
            out += ["| Id | Basis | Sources | Statement | Why only inferred | Mock |", "|---|---|---|---|---|---|"]
            out += [
                f"| {f.id} | {f.basis} | {'; '.join(f.sources)} | {f.statement} | {f.reasoning} | "
                f"{'assumes it' if f.assumed else 'not simulated'} |"
                for f in facts
            ]
        else:
            out += ["| Id | Statement | How to find out | Mock |", "|---|---|---|---|"]
            out += [
                f"| {f.id} | {f.statement} | {f.verify} | {'assumes an answer' if f.assumed else 'not simulated'} |"
                for f in facts
            ]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    from ibos_kit.paths import DOCS

    (DOCS / "evidence.md").write_text(render_matrix())
    print(f"wrote {DOCS / 'evidence.md'}")
