"""Changelog fragments: one small file per change, compiled into the package at release.

A pull request adds a Markdown file with a short front matter block to the
component's `changelog.d/` directory. Nobody edits a shared file, so parallel
pull requests never conflict, and the version is stamped when the release is
cut (`release`), not typed by the author.

    changelog.d/20261013-ztp-driver-choice.md
    ---
    kind: added
    title: Choose which driver a ZTP method uses
    refs: #314
    ---
    Each ZTP method now has a driver setting under ZTP > Methods ...

`release` moves the fragments into `<package>/changelog.json`, which the
backend serves and aggregates (see acex.changelog.service). A component is
found by a `changelog.d/` directory beside a `pyproject.toml` (a Python
package) or a `package.json` (the web interface, which ships its compiled
file inside its bundle).

The product's highlights and roadmap are not fragments and not per package.
They are two Markdown files in `backend/src/acex/changelog/content/`, read as
they are by the backend (nothing is compiled): `highlights.md`, written
together when a release is cut, and `roadmap.md`, kept by one person. `brief`
prints what whoever writes the highlights needs.

This module is deliberately standalone (standard library only, no imports from
the rest of `acex`), so `scripts/changelog.py` can run it from a bare checkout
in CI, and a third-party driver repository can copy or run the single file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

SCHEMA_VERSION = 1
FRAGMENT_DIR = "changelog.d"
OUTPUT_NAME = "changelog.json"
#: The product's highlights and roadmap, read as they are: not compiled, so editing one needs no tool.
#: Relative to the repository root; the backend reads the same directory from its own package.
CONTENT_PATH = Path("backend/src/acex/changelog/content")
HIGHLIGHTS_FILE = "highlights.md"
ROADMAP_FILE = "roadmap.md"
ROADMAP_FIELDS = ("status", "when", "version", "refs")

#: Kinds in the order they are shown. `internal` satisfies the pull request
#: check without being published: for work users cannot notice.
KINDS = ("security", "removed", "added", "changed", "fixed", "deprecated")
INTERNAL = "internal"
AUDIENCES = ("user", "admin", "developer")
#: How a roadmap status is written in roadmap.md (the words people use) and what the backend calls it.
STATUS_WORDS = {
    "considering": "considering",
    "planned": "planned",
    "in progress": "in_progress",
    "in_progress": "in_progress",
    "preview": "preview",
}
TITLE_MAX = 80
SUMMARY_MAX = 200
HIGHLIGHT_MAX = 400
#: A highlight may be dated a little ahead of today (a release written up before it ships), not years.
HIGHLIGHT_AHEAD_DAYS = 31

#: Paths inside a component that do not call for a changelog entry on their own.
EXEMPT_PATHS = (FRAGMENT_DIR, "tests", "README.md", "README", "poetry.lock", "uv.lock")
#: Directories never scanned for components.
SKIPPED_DIRS = {"node_modules", "dist", "build", "site", "__pycache__"}

# A title that is really a commit subject or branch name, like "Feat/ztp backend".
_JARGON = re.compile(r"^(feat|fix|chore|docs|refactor|ci|test|perf|build|style)\s*[(/:!]", re.IGNORECASE)
_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", re.DOTALL)
_SLUG = re.compile(r"[^a-z0-9]+")
_HEADING = re.compile(r"^##[ \t]+(\S.*?)[ \t]*$")
_DATED_HEADING = re.compile(r"^(\d{4}-\d{2}-\d{2})[ \t]*(?:[-–—:·][ \t]*)?(\S.*)$")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
#: One word, a colon and a value: the shape of a `Status: planned` line in roadmap.md.
_FIELD_LINE = re.compile(r"^[ \t]*([A-Za-z]+)[ \t]*:[ \t]*(.*?)[ \t]*$")
#: The line that holds a component's version, by the name of its manifest.
_VERSION_LINE = {
    "pyproject.toml": re.compile(r'^(version\s*=\s*")([^"]+)(")', re.MULTILINE),
    "package.json": re.compile(r'^(\s*"version"\s*:\s*")([^"]+)(")', re.MULTILINE),
}


class FragmentError(ValueError):
    """A fragment, content file or compiled file that cannot be used, with the file named."""


@dataclass
class Component:
    """A package that keeps its own changelog: a `changelog.d/` beside its `pyproject.toml` or `package.json`."""

    id: str
    name: str
    root: Path
    version: str
    output: Path
    #: The file that holds the version.
    manifest_name: str = "pyproject.toml"
    #: Paths below `root` whose changes call for an entry. Empty: every path except the exempt ones.
    paths: tuple[str, ...] = ()

    @property
    def fragments_dir(self) -> Path:
        return self.root / FRAGMENT_DIR

    @property
    def manifest(self) -> Path:
        return self.root / self.manifest_name


@dataclass
class Report:
    """What a command found: problems to fix, and notes worth printing."""

    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover(repo: Path) -> list[Component]:
    """Every component under `repo`, found by its `changelog.d/` directory."""
    components = []
    for dirpath, dirnames, _ in os.walk(repo):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIPPED_DIRS and not d.startswith("."))
        if FRAGMENT_DIR not in dirnames:
            continue
        root = Path(dirpath)
        if (root / "pyproject.toml").exists():
            components.append(_from_pyproject(root))
        elif (root / "package.json").exists():
            components.append(_from_package_json(root))
    return sorted(components, key=lambda c: c.id)


def _from_pyproject(root: Path) -> Component:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    poetry = data.get("tool", {}).get("poetry", {})
    project = data.get("project", {})
    dist_name = poetry.get("name") or project.get("name")
    version = poetry.get("version") or project.get("version")
    if not dist_name or not version:
        raise FragmentError(f"{root / 'pyproject.toml'}: needs a package name and version")
    packages = poetry.get("packages") or [{"include": dist_name.replace("-", "_"), "from": "src"}]
    package_dir = root / packages[0].get("from", ".") / packages[0]["include"]
    options = data.get("tool", {}).get("acex", {}).get("changelog", {})
    return Component(
        id=dist_name,
        name=options.get("name") or dist_name,
        root=root,
        version=version,
        output=package_dir / OUTPUT_NAME,
        paths=tuple(options.get("paths", ())),
    )


def _from_package_json(root: Path) -> Component:
    """A JavaScript project. Its options sit under `acex.changelog` in `package.json`:

    `name` (shown to users), `output` (the compiled file, relative to the project; it must
    end up in the bundle) and `paths` (what changes call for an entry).
    """
    manifest = root / "package.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FragmentError(f"{manifest}: not valid JSON ({exc})") from exc
    name, version = data.get("name"), data.get("version")
    if not name or not version:
        raise FragmentError(f"{manifest}: needs a name and a version")
    options = data.get("acex", {}).get("changelog", {})
    return Component(
        id=name,
        name=options.get("name") or name,
        root=root,
        version=version,
        output=root / options.get("output", OUTPUT_NAME),
        manifest_name="package.json",
        paths=tuple(options.get("paths", ())),
    )


def find(components: list[Component], ref: str) -> Component:
    """A component by id or by the directory it lives in (relative to the repo)."""
    for component in components:
        if ref in (component.id, component.root.name) or Path(ref).resolve() == component.root.resolve():
            return component
    known = ", ".join(c.id for c in components) or "none found"
    raise FragmentError(f"No component '{ref}' has a {FRAGMENT_DIR}/ directory (known: {known})")


# ---------------------------------------------------------------------------
# Fragments
# ---------------------------------------------------------------------------


def _unquote(value: str) -> str:
    """Remove one pair of quotes that wraps the whole value; quotes inside it are text."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1].strip()
    return value


def parse_front_matter(path: Path) -> tuple[dict[str, str], str]:
    """The `key: value` lines between the `---` markers, and the Markdown body after them."""
    match = _FRONT_MATTER.match(path.read_text(encoding="utf-8"))
    if match is None:
        raise FragmentError(f"{path}: must start with a '---' front matter block (see changelog.d/README.md)")
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep or not key.strip():
            raise FragmentError(f"{path}: cannot read '{line.strip()}', expected 'key: value'")
        meta[key.strip().lower()] = _unquote(value)
    return meta, match.group(2).strip()


def _refs(value: str) -> list[dict[str, str | None]]:
    """`refs: #316, ADO-1234 https://dev.azure.com/...` -> labels with optional URLs."""
    refs = []
    for item in (part.strip() for part in value.split(",")):
        if not item:
            continue
        label, _, url = item.partition(" ")
        if label.startswith(("http://", "https://")) and not url:
            label, url = label.rstrip("/").rsplit("/", 1)[-1], label
        refs.append({"label": label, "url": url.strip() or None})
    return refs


def _flag(path: Path, meta: dict[str, str], key: str) -> bool:
    value = meta.get(key, "false").lower()
    if value not in ("true", "false", "yes", "no"):
        raise FragmentError(f"{path}: '{key}' must be true or false, not '{meta[key]}'")
    return value in ("true", "yes")


def _check_title(title: str, where: str) -> str:
    if not title:
        raise FragmentError(f"{where}: 'title' is required: one line a network engineer understands")
    if len(title) > TITLE_MAX:
        raise FragmentError(f"{where}: title is {len(title)} characters, keep it under {TITLE_MAX}")
    if _JARGON.match(title):
        raise FragmentError(f"{where}: title '{title}' looks like a commit subject or branch name; describe the change")
    return title


def _title(path: Path, meta: dict[str, str]) -> str:
    return _check_title(meta.get("title", ""), str(path))


def parse_fragment(path: Path) -> dict:
    """One change as it will appear in the changelog. `kind: internal` is parsed but never published."""
    meta, body = parse_front_matter(path)
    kind = meta.get("kind", "")
    if kind not in (*KINDS, INTERNAL):
        raise FragmentError(f"{path}: 'kind' must be one of {', '.join(KINDS)} or {INTERNAL}, not '{kind}'")
    audience = meta.get("audience", "user")
    if audience not in AUDIENCES:
        raise FragmentError(f"{path}: 'audience' must be one of {', '.join(AUDIENCES)}, not '{audience}'")
    unknown = set(meta) - {"kind", "title", "audience", "breaking", "refs"}
    if unknown:
        raise FragmentError(f"{path}: unknown front matter field(s): {', '.join(sorted(unknown))}")
    return {
        "id": path.stem,
        "kind": kind,
        "title": _title(path, meta),
        "description": body or None,
        "breaking": _flag(path, meta, "breaking"),
        "audience": audience,
        "refs": _refs(meta.get("refs", "")),
    }


def parse_day(text: str, where: str) -> date:
    """`YYYY-MM-DD` and nothing else, a real day, and not far ahead."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text or ""):
        raise FragmentError(
            f"{where}: 'date' is required, as YYYY-MM-DD (not '{text}')"
            if not text
            else f"{where}: the date must be YYYY-MM-DD, not '{text}'"
        )
    try:
        day = date.fromisoformat(text)
    except ValueError as exc:
        raise FragmentError(f"{where}: {text} is not a date") from exc
    if (day - date.today()).days > HIGHLIGHT_AHEAD_DAYS:
        raise FragmentError(f"{where}: {text} is more than {HIGHLIGHT_AHEAD_DAYS} days ahead")
    return day


def _fragment_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.md") if not p.name.upper().startswith("README"))


def fragments(component: Component) -> list[dict]:
    return [parse_fragment(path) for path in _fragment_files(component.fragments_dir)]


def published(entries: list[dict]) -> list[dict]:
    """Entries as they are written to the compiled file: no internal ones."""
    order = {kind: index for index, kind in enumerate(KINDS)}
    kept = [dict(e) for e in entries if e["kind"] != INTERNAL]
    return sorted(kept, key=lambda e: (not e["breaking"], order[e["kind"]], e["title"].lower()))


# ---------------------------------------------------------------------------
# Highlights and roadmap: two files for the whole product
# ---------------------------------------------------------------------------


def _sections(text: str) -> list[tuple[str, str]]:
    """The `## heading` blocks of a Markdown file as (heading, body).

    What comes before the first heading is for whoever edits the file. HTML comments are left out everywhere,
    so a note to the next editor can sit anywhere.
    """
    sections: list[tuple[str, list[str]]] = []
    for line in _HTML_COMMENT.sub("", text).splitlines():
        match = _HEADING.match(line)
        if match:
            sections.append((match.group(1), []))
        elif sections:
            sections[-1][1].append(line)
    return [(heading, "\n".join(lines).strip()) for heading, lines in sections]


def read_highlights(path: Path) -> tuple[list[dict], list[str]]:
    """The product's highlights, newest first, and the problems that kept entries out (each names its heading).

    A heading is the day the feature arrived and what people would call it: `## 2026-10-05 ZTP for Cisco
    switches`. The text below is one or two sentences. No components or versions: the page leads from a
    highlight to nothing, and the releases are listed under Details.
    """
    if not path.exists():
        return [], []
    found: list[dict] = []
    problems: list[str] = []
    seen: set[str] = set()
    for heading, body in _sections(path.read_text(encoding="utf-8")):
        where = f"{path}: '## {heading}'"
        match = _DATED_HEADING.match(heading)
        if match is None:
            problems.append(f"{where} must start with the day it arrived, like '## 2026-10-05 ZTP for Cisco switches'")
            continue
        try:
            day = parse_day(match.group(1), where)
            title = _check_title(match.group(2).strip(), where)
        except FragmentError as exc:
            problems.append(str(exc))
            continue
        if len(body) > HIGHLIGHT_MAX:
            problems.append(f"{where}: the text is {len(body)} characters, keep it under {HIGHLIGHT_MAX}")
            continue
        identity = f"{day:%Y%m%d}-{slugify(title)}"
        if identity in seen:
            problems.append(f"{where}: there is already a highlight with this date and title")
            continue
        seen.add(identity)
        found.append(
            {"id": identity, "date": day.isoformat(), "title": title, "description": body or None, "components": []}
        )
    found.sort(key=lambda h: h["title"].casefold())
    found.sort(key=lambda h: h["date"], reverse=True)  # stable: the same day stays in title order
    return found, problems


def _roadmap_fields(body: str, where: str) -> tuple[dict[str, str], str]:
    """The block of `Status: planned` style lines directly under a roadmap heading, and the text after it.

    A first paragraph that is not made of such lines is all explanation. One that is, but names a field this
    file does not have, is a typo worth stopping for (`Staus: planned`).
    """
    parts = re.split(r"\n[ \t]*\n", body, maxsplit=1)
    first, rest = parts[0], parts[1] if len(parts) > 1 else ""
    lines = [line for line in first.splitlines() if line.strip()]
    shaped = [_FIELD_LINE.match(line) for line in lines]
    if not lines or not all(shaped):
        return {}, body
    fields: dict[str, str] = {}
    for match in shaped:
        key = match.group(1).lower()
        if key not in ROADMAP_FIELDS:
            known = ", ".join(field.capitalize() for field in ROADMAP_FIELDS)
            raise FragmentError(f"{where}: unknown field '{match.group(1)}' (known: {known})")
        fields[key] = match.group(2)
    return fields, rest.strip()


def read_roadmap(path: Path) -> tuple[list[dict], list[str]]:
    """The planned work in the order it is written, and the problems that kept entries out.

    A heading names the feature. Directly below it an optional block of `Status:`, `When:`, `Version:` and
    `Refs:` lines (the status is `planned` when left out), then the explanation, which is all that most
    items need. Nothing per package: the roadmap is the product's.
    """
    if not path.exists():
        return [], []
    found: list[dict] = []
    problems: list[str] = []
    seen: set[str] = set()
    for heading, body in _sections(path.read_text(encoding="utf-8")):
        where = f"{path}: '## {heading}'"
        try:
            title = _check_title(heading, where)
            fields, description = _roadmap_fields(body, where)
        except FragmentError as exc:
            problems.append(str(exc))
            continue
        word = fields.get("status", "planned").strip().lower()
        status = STATUS_WORDS.get(word)
        if status is None:
            options = ", ".join(w for w in STATUS_WORDS if "_" not in w)
            problems.append(f"{where}: Status must be one of {options}, not '{fields['status']}'")
            continue
        identity = slugify(title)
        if identity in seen:
            problems.append(f"{where}: there is already an item with this title")
            continue
        seen.add(identity)
        found.append(
            {
                "id": identity,
                "title": title,
                "description": description or None,
                "status": status,
                "planned_version": fields.get("version") or None,
                "planned_date": fields.get("when") or None,
                "components": [],
                "refs": _refs(fields.get("refs", "")),
            }
        )
    return found, problems


def content_problems(content: Path) -> list[str]:
    """Everything wrong in the highlights and the roadmap, for `validate` and the pull request check."""
    return [*read_highlights(content / HIGHLIGHTS_FILE)[1], *read_roadmap(content / ROADMAP_FILE)[1]]


# ---------------------------------------------------------------------------
# Compiled file
# ---------------------------------------------------------------------------


def read_compiled(component: Component) -> dict:
    """The component's compiled changelog, or an empty one if it has not been released with entries yet."""
    if not component.output.exists():
        return {"schema_version": SCHEMA_VERSION, "component": component.id, "name": component.name, "releases": []}
    try:
        data = json.loads(component.output.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FragmentError(f"{component.output}: not valid JSON ({exc})") from exc
    if data.get("component") != component.id:
        raise FragmentError(f"{component.output}: belongs to '{data.get('component')}', not '{component.id}'")
    return data


def compiled(component: Component, *, include_unreleased: bool = False) -> dict:
    """The compiled file as it should be: released entries kept, and the pending ones when asked for.

    `coming` and `highlights` stay in the file format, empty: the product's own are served from `content/`.
    """
    data = read_compiled(component)
    releases = [r for r in data.get("releases", []) if r.get("version") is not None]
    if include_unreleased:
        pending = published(fragments(component))
        if pending:
            releases = [{"version": None, "date": None, "entries": pending}, *releases]
    return {
        "schema_version": SCHEMA_VERSION,
        "component": component.id,
        "name": component.name,
        "releases": releases,
        "coming": [],
        "highlights": [],
    }


def _dump(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_compiled(component: Component, data: dict) -> bool:
    """Write the file; True when its content changed."""
    text = _dump(data)
    if component.output.exists() and component.output.read_text(encoding="utf-8") == text:
        return False
    component.output.parent.mkdir(parents=True, exist_ok=True)
    component.output.write_text(text, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def slugify(text: str) -> str:
    """A file name part: letters folded to ASCII (ä to a), words kept whole, at most 40 characters."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = _SLUG.sub("-", folded.lower()).strip("-")
    if len(slug) > 40:
        head = slug[:41]
        slug = head[:40] if head.endswith("-") or "-" not in head else head.rsplit("-", 1)[0]
    return slug or "change"


def new_fragment(component: Component, *, kind: str, title: str, body: str = "", slug: str | None = None) -> Path:
    """Create a fragment file for a change, named so that two authors never pick the same file."""
    stem = f"{date.today():%Y%m%d}-{slugify(slug) if slug else slugify(title)}"
    path = component.fragments_dir / f"{stem}.md"
    if path.exists():
        raise FragmentError(f"{path} already exists; pass --slug to name this one differently")
    component.fragments_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nkind: {kind}\ntitle: {title}\n---\n{body.strip()}\n", encoding="utf-8")
    try:
        parse_fragment(path)
    except FragmentError:
        path.unlink()  # a rejected note must not stay behind and break everything after it
        raise
    return path


def validate(components: list[Component], content: Path | None = None) -> Report:
    """Every fragment and compiled file of every component parses, and so do the highlights and the roadmap
    in `content` (left alone when it is not given or the repository has none)."""
    report = Report()
    if content is not None:
        report.errors.extend(content_problems(content))
    for component in components:
        for reader in (fragments, read_compiled):
            try:
                reader(component)
            except FragmentError as exc:
                report.errors.append(str(exc))
        try:
            for release_ in read_compiled(component).get("releases", []):
                text = release_.get("summary") or ""
                if len(text) > SUMMARY_MAX:
                    report.errors.append(
                        f"{component.output}: the summary of {release_.get('version')} is {len(text)} characters, "
                        f"keep it under {SUMMARY_MAX}"
                    )
        except FragmentError:
            pass  # already reported above
    return report


def build(components: list[Component], *, include_unreleased: bool = False, check: bool = False) -> Report:
    """Regenerate every compiled file. With `check`, only report the ones that are out of date."""
    report = Report()
    for component in components:
        try:
            data = compiled(component, include_unreleased=include_unreleased)
        except FragmentError as exc:
            report.errors.append(str(exc))
            continue
        if check:
            current = component.output.read_text(encoding="utf-8") if component.output.exists() else ""
            if current != _dump(data):
                report.errors.append(f"{component.output} is out of date: run `changelog.py build` and commit it")
        elif write_compiled(component, data):
            report.notes.append(f"wrote {component.output}")
    return report


def bump(version: str, how: str, entries: list[dict]) -> str:
    """The next version: `auto` reads the entries (breaking -> major, new or changed -> minor, else patch)."""
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise FragmentError(f"Cannot bump '{version}': only plain MAJOR.MINOR.PATCH versions are bumped automatically")
    major, minor, patch = (int(p) for p in parts)
    if how == "auto":
        kinds = {e["kind"] for e in entries}
        if any(e["breaking"] for e in entries):
            how = "major"
        elif kinds & {"added", "changed", "removed", "deprecated"}:
            how = "minor"
        else:
            how = "patch"
    if how == "major":
        return f"{major + 1}.0.0"
    if how == "minor":
        return f"{major}.{minor + 1}.0"
    if how == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise FragmentError(f"Unknown bump '{how}'")


def set_version(component: Component, version: str) -> None:
    """Write the version into the manifest (and, for a JavaScript project, into its lock file)."""
    text = component.manifest.read_text(encoding="utf-8")
    new_text, count = _VERSION_LINE[component.manifest_name].subn(
        lambda m: f"{m.group(1)}{version}{m.group(3)}", text, count=1
    )
    if count != 1:
        raise FragmentError(f"{component.manifest}: no version line to update")
    component.manifest.write_text(new_text, encoding="utf-8")
    if component.manifest_name == "package.json":
        _set_lock_version(component.root / "package-lock.json", component.version, version)
    component.version = version


def _set_lock_version(lock: Path, old: str, new: str) -> None:
    """npm repeats the project's own version in the lock file, twice at the top; keep them in step."""
    if not lock.exists():
        return
    pattern = re.compile(rf'("version"\s*:\s*"){re.escape(old)}(")')
    text = lock.read_text(encoding="utf-8")
    lock.write_text(pattern.sub(lambda m: f"{m.group(1)}{new}{m.group(2)}", text, count=2), encoding="utf-8")


def release(
    component: Component,
    *,
    version: str | None = None,
    bump_how: str | None = None,
    on: date | None = None,
    summary: str | None = None,
) -> Report:
    """Stamp the pending fragments with a version and date, and move them into the compiled file.

    The version comes from the manifest (already bumped by the releaser), from
    `--bump`, which bumps the manifest too, or from `--version`.
    Nothing is typed into the entries themselves. `summary` is the one sentence
    a reader who wants the gist sees above the entries; it is written here, by
    whoever cuts the release, not in a fragment.
    """
    report = Report()
    summary = " ".join(summary.split()) if summary else None
    if summary and len(summary) > SUMMARY_MAX:
        report.errors.append(f"summary is {len(summary)} characters, keep it under {SUMMARY_MAX}: one sentence")
        return report
    pending = fragments(component)
    if not pending:
        report.errors.append(f"{component.id}: nothing to release, {component.fragments_dir} has no fragments")
        return report
    entries = published(pending)
    data = read_compiled(component)
    if bump_how:
        version = bump(component.version, bump_how, entries)
        set_version(component, version)
        report.notes.append(f"{component.manifest}: version {version}")
    version = version or component.version
    if any(r.get("version") == version for r in data.get("releases", [])):
        report.errors.append(
            f"{component.id}: version {version} is already in {component.output}; bump the version first "
            f"(edit {component.manifest_name} or pass --bump)"
        )
        return report

    releases = [r for r in data.get("releases", []) if r.get("version") is not None]
    if entries:
        new_release = {"version": version, "date": (on or date.today()).isoformat()}
        if summary:
            new_release["summary"] = summary
        releases.insert(0, {**new_release, "entries": entries})
    else:
        report.notes.append(f"{component.id}: only internal fragments; {version} gets no entries")
        if summary:
            report.notes.append(f"{component.id}: the summary was not stored, there is nothing to summarise")
    data.update(component=component.id, name=component.name, releases=releases, coming=[], highlights=[])
    data["schema_version"] = SCHEMA_VERSION
    write_compiled(component, data)
    for path in _fragment_files(component.fragments_dir):
        path.unlink()
    report.notes.append(
        f"{component.id} {version}: {len(entries)} entr{'y' if len(entries) == 1 else 'ies'} -> {component.output}"
    )
    return report


def _is_exempt(relative: Path, paths: tuple[str, ...] = ()) -> bool:
    """A path that does not call for an entry. A component that lists its `paths` counts only those."""
    if not relative.parts:
        return True
    if paths:
        return not any(relative.parts[: len(Path(p).parts)] == Path(p).parts for p in paths)
    return relative.parts[0] in EXEMPT_PATHS


def check(
    components: list[Component],
    changed: list[tuple[str, str]],
    repo: Path,
    *,
    release_ready: bool = False,
    base_versions: dict[str, str] | None = None,
) -> Report:
    """A pull request that changes a component adds a fragment for it.

    `changed` is `git diff --name-status` as (status, path) pairs. With
    `release_ready` (pull requests into the release branch), a component whose
    version differs from the target branch's (`base_versions`, what the
    pipeline will publish) must have had its fragments released, so the
    version being published carries its notes. A component unknown to the
    target branch is about to be published for the first time.
    """
    report = validate(components, content=repo / CONTENT_PATH)
    for component in components:
        try:
            root = component.root.resolve().relative_to(repo.resolve())
        except ValueError:
            continue
        touched = added_fragment = False
        for status, path in changed:
            relative = Path(path)
            if relative.is_relative_to(CONTENT_PATH):
                continue  # the highlights and the roadmap are edited on their own, with no entry for it
            if root != Path(".") and not relative.is_relative_to(root):
                continue
            inside = relative.relative_to(root) if root != Path(".") else relative
            if inside.parts[:1] == (FRAGMENT_DIR,):
                # Only a file directly in the directory is a change note, and not its README.
                if len(inside.parts) == 2 and inside.suffix == ".md" and not inside.name.upper().startswith("README"):
                    added_fragment |= status.startswith("A")
            elif not _is_exempt(inside, component.paths):
                touched = True
        if touched and not added_fragment:
            report.errors.append(
                f"{component.id}: changed without a changelog entry. Add one with\n"
                f'    python scripts/changelog.py new {component.id} --kind <{"|".join(KINDS)}> --title "..."\n'
                f"  or `--kind {INTERNAL}` when users cannot notice the change."
            )
        if release_ready:
            try:
                pending = published(fragments(component))
            except FragmentError:
                continue  # already reported by validate()
            publishing = component.version != (base_versions or {}).get(component.id)
            if pending and publishing:
                report.errors.append(
                    f"{component.id}: version {component.version} is about to be published but "
                    f"{len(pending)} fragment(s) are not released. Run\n"
                    f"    python scripts/changelog.py release {component.id}\n"
                    f"  (stamps the version in {component.manifest_name}; add --bump if that version is already out)."
                )
    return report


def git_versions_at(repo: Path, ref: str, components: list[Component]) -> dict[str, str]:
    """Each component's version in its manifest at `ref`; left out when the file is not there."""
    versions = {}
    for component in components:
        path = component.manifest.resolve().relative_to(repo.resolve()).as_posix()
        result = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=repo, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            continue
        try:
            if component.manifest_name == "package.json":
                version = json.loads(result.stdout).get("version")
            else:
                data = tomllib.loads(result.stdout)
                poetry, project = data.get("tool", {}).get("poetry", {}), data.get("project", {})
                version = poetry.get("version") or project.get("version")
        except (json.JSONDecodeError, tomllib.TOMLDecodeError):
            continue
        if version:
            versions[component.id] = version
    return versions


def git_changed(repo: Path, base: str) -> list[tuple[str, str]]:
    """`git diff --name-status` from the merge base with `base`, as (status, path) pairs."""
    result = subprocess.run(
        ["git", "diff", "--name-status", "--no-renames", f"{base}...HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise FragmentError(f"git diff against '{base}' failed: {result.stderr.strip()}")
    pairs = []
    for line in result.stdout.splitlines():
        status, _, path = line.partition("\t")
        if path:
            pairs.append((status, path))
    return pairs


# ---------------------------------------------------------------------------
# Brief for whoever writes the highlights
# ---------------------------------------------------------------------------

BRIEF_GIST_MAX = 160


def _gist(text: str | None) -> str:
    """The first sentence of an entry's description, short enough to scan."""
    if not text:
        return ""
    sentence = re.split(r"(?<=[.!?])\s", " ".join(text.split()), maxsplit=1)[0]
    return sentence if len(sentence) <= BRIEF_GIST_MAX else sentence[: BRIEF_GIST_MAX - 1].rstrip() + "…"


def _brief_entries(entries: list[dict]) -> list[str]:
    lines = []
    for entry in entries:
        if entry.get("audience", "user") == "developer":
            continue  # a highlight is for the people who use and run ACEX
        gist = _gist(entry.get("description"))
        flag = " (breaking)" if entry.get("breaking") else ""
        lines.append(f"- [{entry['kind']}] {entry['title']}{flag}" + (f" - {gist}" if gist else ""))
    return lines


def brief(components: list[Component], content: Path, *, since: date | None = None) -> str:
    """What whoever writes the highlights for a release needs, as Markdown: what a highlight is and how to
    write one, what is already published, the planned work, and what changed since the newest highlight.

    The tool only collects. A person, or the assistant they work with, writes the highlights from it.
    """
    published_highlights, _ = read_highlights(content / HIGHLIGHTS_FILE)
    planned, _ = read_roadmap(content / ROADMAP_FILE)
    start = since.isoformat() if since else (published_highlights[0]["date"] if published_highlights else None)
    target = (CONTENT_PATH / HIGHLIGHTS_FILE).as_posix()
    out = [
        "# Highlights for the next release",
        "",
        f"Write the highlights for ACEX's What's new page and add them to `{target}`. Change nothing else.",
        "",
        "## What a highlight is",
        "",
        "- A feature or improvement that people who use or run ACEX would recognise, in their words:",
        '  "ZTP for Cisco switches", not "ZTP script URL moved".',
        f"- One or two sentences, at most {HIGHLIGHT_MAX} characters. No versions, package names or ticket numbers.",
        "- Dated the day it arrived: the release date, unless the changes below say otherwise.",
        "- Related changes make one highlight. Leave out fixes, internal work and what only developers see.",
        "- Usually three to six per release. None is fine when nothing stands out.",
        "",
        "## Format",
        "",
        "```markdown",
        "## 2026-10-05 ZTP for Cisco switches",
        "",
        "A new, unconfigured Cisco switch can download its bootstrap from ACEX and be given its rendered",
        "configuration. The web interface has a ZTP section for following it.",
        "```",
        "",
        "Newest first. When done, run `python scripts/changelog.py validate`.",
        "",
        "## Already published, newest first",
        "",
    ]
    out += [f"- {h['date']} {h['title']}" for h in published_highlights[:8]] or ["- (none yet)"]
    out += ["", "## On the roadmap", ""]
    out += [f"- {item['title']} ({item['status'].replace('_', ' ')})" for item in planned] or ["- (empty)"]
    out += [
        "",
        "If a highlight delivers one of these, say so in the pull request: the person who keeps the roadmap",
        f"removes it from `{(CONTENT_PATH / ROADMAP_FILE).as_posix()}`.",
        "",
        f"## Changes since {start}" if start else "## All changes",
        "",
    ]
    shown = False
    for component in components:
        sections: list[tuple[str, list[dict], str | None]] = []
        pending = published(fragments(component))
        if pending:
            sections.append((f"{component.id} (not released yet)", pending, None))
        for release_ in read_compiled(component).get("releases", []):
            if release_.get("version") is None or (start and (release_.get("date") or "") < start):
                continue
            title = f"{component.id} {release_['version']} ({release_.get('date')})"
            sections.append((title, release_.get("entries", []), release_.get("summary")))
        for title, entries, summary in sections:
            lines = _brief_entries(entries)
            if not lines:
                continue
            shown = True
            out += [f"### {title}", ""]
            out += [f"_{summary}_", ""] if summary else []
            out += [*lines, ""]
    if not shown:
        out += ["Nothing for users or administrators since then.", ""]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="changelog.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", type=Path, default=None, help="repository root (default: the current directory)")
    commands = parser.add_subparsers(dest="command", required=True)

    new = commands.add_parser("new", help="create a fragment for a change")
    new.add_argument("component", help="component id (package name) or its directory")
    new.add_argument("--kind", required=True, choices=(*KINDS, INTERNAL))
    new.add_argument("--title", required=True, help="one line, written for the people who use ACEX")
    new.add_argument("--body", default="", help="longer description, Markdown")
    new.add_argument("--slug", default=None, help="file name part (default: from the title)")

    commands.add_parser("validate", help="check every fragment and compiled file, the highlights and the roadmap")
    commands.add_parser("list", help="show components and their pending fragments")

    brief_cmd = commands.add_parser("brief", help="what to write the release's highlights from, as Markdown")
    brief_cmd.add_argument(
        "--since", default=None, help="changes from this day, YYYY-MM-DD (default: newest highlight)"
    )

    build_cmd = commands.add_parser("build", help="regenerate the compiled changelog.json files")
    build_cmd.add_argument("--include-unreleased", action="store_true", help="add pending fragments as 'unreleased'")
    build_cmd.add_argument("--check", action="store_true", help="fail if a compiled file is out of date")

    release_cmd = commands.add_parser("release", help="stamp pending fragments with the version and date")
    release_cmd.add_argument("component")
    release_cmd.add_argument("--version", default=None, help="override the version in the manifest")
    release_cmd.add_argument("--bump", choices=("major", "minor", "patch", "auto"), help="bump the manifest first")
    release_cmd.add_argument("--date", default=None, help="release date, YYYY-MM-DD (default: today)")
    release_cmd.add_argument("--summary", default=None, help="one sentence about the release, shown above its entries")

    check_cmd = commands.add_parser("check", help="pull request check: changed components have a fragment")
    check_cmd.add_argument("--base", required=True, help="the branch the pull request targets, e.g. origin/dev")
    check_cmd.add_argument("--release-ready", action="store_true", help="also require fragments to be released")
    return parser


def _print(report: Report) -> int:
    for note in report.notes:
        print(note)
    for error in report.errors:
        print(f"error: {error}", file=sys.stderr)
    return 0 if report.ok else 1


def main(argv: list[str] | None = None, repo: Path | None = None) -> int:
    args = _parser().parse_args(argv)
    repo = (args.repo or repo or Path.cwd()).resolve()
    try:
        components = discover(repo)
        if args.command == "new":
            component = find(components, args.component)
            path = new_fragment(component, kind=args.kind, title=args.title, body=args.body, slug=args.slug)
            print(f"created {path.relative_to(repo)}; edit it, then commit it with your change")
            return 0
        if args.command == "brief":
            since = parse_day(args.since, "--since") if args.since else None
            print(brief(components, repo / CONTENT_PATH, since=since), end="")
            return 0
        if args.command == "list":
            for component in components:
                pending = fragments(component)
                print(
                    f"{component.id} {component.version} ({component.root.relative_to(repo)}): {len(pending)} pending"
                )
                for entry in pending:
                    print(f"  [{entry['kind']}] {entry['title']}")
            return 0
        if args.command == "validate":
            report = validate(components, content=repo / CONTENT_PATH)
            report.notes.append(f"{len(components)} component(s) checked")
            return _print(report)
        if args.command == "build":
            return _print(build(components, include_unreleased=args.include_unreleased, check=args.check))
        if args.command == "release":
            on = date.fromisoformat(args.date) if args.date else None
            component = find(components, args.component)
            return _print(release(component, version=args.version, bump_how=args.bump, on=on, summary=args.summary))
        if args.command == "check":
            base_versions = git_versions_at(repo, args.base, components) if args.release_ready else None
            changed = git_changed(repo, args.base)
            return _print(
                check(components, changed, repo, release_ready=args.release_ready, base_versions=base_versions)
            )
    except FragmentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
