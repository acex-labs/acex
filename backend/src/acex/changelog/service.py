"""Where release notes come from, and how they are put together.

Three sources, one schema:

- The backend's own `changelog.json`, compiled into the package at release.
- Any installed package that declares an `acex.changelog` entry point whose
  value is the package holding its `changelog.json`. That is how a driver, a
  first-party or a third-party one, publishes its notes without the core team
  knowing about it.
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
    ComponentChangelog,
    ComponentRelease,
    SectionInfo,
    SourceKind,
)
from pydantic import ValidationError

logger = logging.getLogger("acex.changelog")

CHANGELOG_GROUP = "acex.changelog"
FILE_NAME = "changelog.json"

PRODUCT = SectionInfo(id="product", name="ACEX")


class ChangelogService:
    def __init__(
        self,
        *,
        package: str = "acex",
        own_file: Path | None = None,
        extra_dir: Path | None = None,
        entry_points: Callable[..., Iterable] = entry_points,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.package = package
        self.own_file = own_file
        self.extra_dir = extra_dir
        self.entry_points = entry_points
        self.now = now
        self._packaged: list[tuple[ComponentChangelog, SourceKind]] | None = None

    # --- sources -------------------------------------------------------------

    def packaged(self) -> list[tuple[ComponentChangelog, SourceKind]]:
        """The backend's own file and every `acex.changelog` entry point.

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

    # --- GET /changelog ------------------------------------------------------

    def changelog(self) -> ChangelogResponse:
        seen: set[str] = set()
        sections: dict[str, tuple[SectionInfo, list[tuple[ComponentChangelog, SourceKind]]]] = {}
        for changelog, source in [*self.packaged(), *self.deployment()]:
            if changelog.component in seen:
                logger.warning(f"changelog for '{changelog.component}' found twice; keeping the first")
                continue
            seen.add(changelog.component)
            section = PRODUCT if source in (SourceKind.own, SourceKind.package) else changelog.section
            sections.setdefault(section.id, (section, []))[1].append((changelog, source))
        ordered = sorted(sections.values(), key=lambda item: (item[0].id != PRODUCT.id, item[0].name.lower()))
        return ChangelogResponse(
            generated_at=self.now(), sections=[_section(info, members) for info, members in ordered]
        )


def _package_file(package: str) -> Path | None:
    """The `changelog.json` inside an importable package, if there is one."""
    try:
        import_module(package)
        path = resources.files(package) / FILE_NAME
    except Exception as exc:
        logger.warning(f"cannot look for {FILE_NAME} in package '{package}': {exc}")
        return None
    return Path(str(path)) if path.is_file() else None


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
