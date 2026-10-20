"""Where release notes come from, and how they are put together.

Five sources, one schema:

- The product's highlights and roadmap: `content/highlights.md` and
  `content/roadmap.md` in this package, read as they are on every request. They
  belong to the product as a whole, not to a package, and nothing is compiled.
- The backend's own `changelog.json`, compiled into the package at release.
- Any installed package that declares an `acex.changelog` entry point whose
  value is the package holding its `changelog.json`. That is how a driver, a
  first-party or a third-party one, publishes its notes without the core team
  knowing about it.
- Compiled files in the package's `changelog_components/` directory. The image
  build puts them there for the components that run as their own service
  (agents, the worker, the command line) and so are not installed in the
  backend. An installed package wins over a bundled copy of the same component.
- JSON files in ACEX_CHANGELOG_EXTRA_DIR, in the same format plus a `section`.
  They are for one deployment only and are shown apart from the product, so a
  customer's notes never end up in the open product and vice versa.

A source that cannot be read is logged and skipped; the endpoint always answers.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from importlib import import_module, resources
from importlib.metadata import entry_points
from pathlib import Path

from acex.changelog.models import (
    ChangelogComponent,
    ChangelogResponse,
    ChangelogSection,
    ComingFeature,
    ComponentChangelog,
    ComponentRelease,
    Highlight,
    SectionInfo,
    SourceKind,
)
from acex.changelog.tool import HIGHLIGHTS_FILE, ROADMAP_FILE, read_highlights, read_roadmap
from pydantic import ValidationError

logger = logging.getLogger("acex.changelog")

CHANGELOG_GROUP = "acex.changelog"
FILE_NAME = "changelog.json"
BUNDLED_DIR = "changelog_components"
CONTENT_DIR = Path(__file__).resolve().parent / "content"

PRODUCT = SectionInfo(id="product", name="ACEX")


class ChangelogService:
    def __init__(
        self,
        *,
        package: str = "acex",
        own_file: Path | None = None,
        bundled_dir: Path | None = None,
        extra_dir: Path | None = None,
        content_dir: Path | None = None,
        entry_points: Callable[..., Iterable] = entry_points,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.package = package
        self.own_file = own_file
        self.bundled_dir = bundled_dir
        self.extra_dir = extra_dir
        self.content_dir = content_dir or CONTENT_DIR
        self.entry_points = entry_points
        self.now = now
        self._packaged: list[tuple[ComponentChangelog, SourceKind]] | None = None

    # --- sources -------------------------------------------------------------

    def packaged(self) -> list[tuple[ComponentChangelog, SourceKind]]:
        """The backend's own file, every `acex.changelog` entry point and the bundled components.

        Read once: installed packages do not change while the backend runs.
        """
        if self._packaged is None:
            found = []
            own = self.own_file or _package_file(self.package)
            if own is not None:
                found.extend((c, SourceKind.own) for c in _read(own))
            for entry_point in self.entry_points(group=CHANGELOG_GROUP):
                path = _package_file(entry_point.value.partition(":")[0])
                if path is None:
                    logger.warning(
                        f"{CHANGELOG_GROUP} entry point '{entry_point.name}': no {FILE_NAME} in {entry_point.value}"
                    )
                    continue
                found.extend((c, SourceKind.package) for c in _read(path))
            bundled = self.bundled_dir or _package_dir(self.package, BUNDLED_DIR)
            if bundled is not None and bundled.is_dir():
                known = {c.component for c, _ in found}
                for path in sorted(bundled.glob("*.json")):
                    found.extend((c, SourceKind.bundled) for c in _read(path) if c.component not in known)
            self._packaged = found
        return self._packaged

    def deployment(self) -> list[tuple[ComponentChangelog, SourceKind]]:
        """Files in the extra directory. Read on every call: the directory is how a deployment updates its notes."""
        if self.extra_dir is None:
            return []
        if not self.extra_dir.is_dir():
            logger.warning(f"ACEX_CHANGELOG_EXTRA_DIR {self.extra_dir} is not a directory")
            return []
        found = []
        for path in sorted(self.extra_dir.glob("*.json")):
            for changelog in _read(path):
                if changelog.section is None:
                    changelog.section = SectionInfo(id=path.stem, name=path.stem)
                if changelog.section.id == PRODUCT.id:
                    logger.warning(f"{path}: section '{PRODUCT.id}' is reserved for the product; file skipped")
                    continue
                found.append((changelog, SourceKind.directory))
        return found

    def curated(self) -> tuple[list[Highlight], list[ComingFeature]]:
        """The product's highlights and roadmap from the two content files.

        Read on every call: they are small, and a merged edit should be live without a compile step. An entry
        that cannot be read is logged and skipped; it never takes the others with it.
        """
        found, problems = read_highlights(self.content_dir / HIGHLIGHTS_FILE)
        planned, more = read_roadmap(self.content_dir / ROADMAP_FILE)
        for problem in [*problems, *more]:
            logger.warning(f"content skipped: {problem}")
        highlights = [Highlight.model_validate({**item, "id": f"{self.package}/{item['id']}"}) for item in found]
        return highlights, [ComingFeature.model_validate(item) for item in planned]

    # --- GET /changelog ------------------------------------------------------

    def changelog(self) -> ChangelogResponse:
        seen: set[str] = set()
        highlights, roadmap = self.curated()
        sections: dict[str, tuple[SectionInfo, list[tuple[ComponentChangelog, SourceKind]]]] = {}
        if roadmap:
            sections[PRODUCT.id] = (PRODUCT, [])
        for changelog, source in [*self.packaged(), *self.deployment()]:
            if changelog.component in seen:
                logger.warning(f"changelog for '{changelog.component}' found twice; keeping the first")
                continue
            seen.add(changelog.component)
            if source != SourceKind.directory:
                # The file stem is only unique within one component; the component makes it unique here.
                highlights.extend(
                    h.model_copy(update={"id": f"{changelog.component}/{h.id}"}) for h in changelog.highlights
                )
            section = PRODUCT if source != SourceKind.directory else changelog.section
            sections.setdefault(section.id, (section, []))[1].append((changelog, source))
        ordered = sorted(sections.values(), key=lambda item: (item[0].id != PRODUCT.id, item[0].name.lower()))
        # The newest first; a deployment's own notes have none, so they are not part of the product's story.
        highlights.sort(key=lambda h: h.title.casefold())
        highlights.sort(key=lambda h: h.date, reverse=True)  # stable: the same day stays in title order
        built = [_section(info, members) for info, members in ordered]
        for section in built:
            if section.id == PRODUCT.id:
                section.coming = [*roadmap, *section.coming]
        return ChangelogResponse(generated_at=self.now(), highlights=highlights, sections=built)


def _package_file(package: str) -> Path | None:
    """The `changelog.json` inside an importable package, if there is one."""
    try:
        import_module(package)
        path = resources.files(package) / FILE_NAME
    except Exception as exc:
        logger.warning(f"cannot look for {FILE_NAME} in package '{package}': {exc}")
        return None
    return Path(str(path)) if path.is_file() else None


def _package_dir(package: str, name: str) -> Path | None:
    """A directory inside an importable package, if there is one."""
    try:
        path = resources.files(package) / name
    except Exception as exc:
        logger.warning(f"cannot look for {name} in package '{package}': {exc}")
        return None
    return Path(str(path)) if path.is_dir() else None


def _read(path: Path) -> list[ComponentChangelog]:
    """The changelog in a file, or nothing (logged) when it cannot be used."""
    try:
        return [ComponentChangelog.model_validate_json(path.read_text(encoding="utf-8"))]
    except (OSError, ValueError, ValidationError) as exc:
        logger.warning(f"{path}: changelog skipped: {exc}")
        return []


def _section(info: SectionInfo, members: list[tuple[ComponentChangelog, SourceKind]]) -> ChangelogSection:
    releases = [
        ComponentRelease(component=changelog.component, **release.model_dump())
        for changelog, _ in members
        for release in changelog.releases
    ]
    # Unreleased first, then newest; the component name breaks ties so the order is stable.
    names = {changelog.component: changelog.name for changelog, _ in members}
    releases.sort(key=lambda r: (r.version is not None, -(r.date.toordinal() if r.date else 0), names[r.component]))
    return ChangelogSection(
        id=info.id,
        name=info.name,
        components=[ChangelogComponent(id=c.component, name=c.name, source=source) for c, source in members],
        releases=releases,
        coming=[item for changelog, _ in members for item in changelog.coming],
    )
