"""What the changelog endpoint answers, and the file format behind it.

`ComponentChangelog` is the compiled `changelog.json` that every component
ships inside its package (built by acex.changelog.tool). The same shape, with
a `section`, is what a deployment drops into ACEX_CHANGELOG_EXTRA_DIR for
notes that must never be part of the product. The API response below is an
aggregate of those files.
"""

import datetime
import logging
from enum import StrEnum

from pydantic import BaseModel, ValidationError, field_validator

logger = logging.getLogger("acex.changelog")

SCHEMA_VERSION = 1


class EntryKind(StrEnum):
    security = "security"
    removed = "removed"
    added = "added"
    changed = "changed"
    fixed = "fixed"
    deprecated = "deprecated"


class Audience(StrEnum):
    """Who the entry is written for. The UI shows user and admin entries; developer ones are for integrators."""

    user = "user"
    admin = "admin"
    developer = "developer"


class SourceKind(StrEnum):
    """Where the backend got the notes from."""

    #: The backend itself.
    own = "self"
    #: A Python package installed in the backend process (an `acex.changelog` entry point).
    package = "package"
    #: A component that runs as its own service (an agent, the worker, the command line), whose
    #: compiled file was put into the backend image when it was built.
    bundled = "bundled"
    #: A file in ACEX_CHANGELOG_EXTRA_DIR, put there by whoever runs this deployment.
    directory = "directory"


class Reference(BaseModel):
    """A pointer to a pull request or work item, shown as a label; the URL is optional."""

    label: str
    url: str | None = None


class ChangelogEntry(BaseModel):
    id: str
    kind: EntryKind
    #: One line, written for the people who use ACEX.
    title: str
    #: Markdown. Rendered without raw HTML.
    description: str | None = None
    breaking: bool = False
    audience: Audience = Audience.user
    refs: list[Reference] = []


class ChangelogRelease(BaseModel):
    #: None means not released yet: a development build carrying pending entries.
    version: str | None = None
    date: datetime.date | None = None
    #: One sentence on what the release is about, for the reader who wants the gist. Written when the release is cut.
    summary: str | None = None
    entries: list[ChangelogEntry] = []


class ComingStatus(StrEnum):
    #: Weighed but not decided: shown so that people can see what is on the table.
    considering = "considering"
    planned = "planned"
    in_progress = "in_progress"
    preview = "preview"


class ComingFeature(BaseModel):
    id: str
    title: str
    description: str | None = None
    status: ComingStatus = ComingStatus.planned
    planned_version: str | None = None
    #: Free text on purpose: "2026-11", "Q1 2027" and a date are all honest answers.
    planned_date: str | None = None
    #: The components the item touches, by id; an item usually spans several.
    components: list[str] = []
    refs: list[Reference] = []


class SectionInfo(BaseModel):
    """Which list the notes belong to. The product is one section; a deployment's own notes are another."""

    id: str
    name: str


class HighlightComponent(BaseModel):
    """A component, and optionally the version of it, that a highlight is delivered in."""

    component: str
    version: str | None = None


class Highlight(BaseModel):
    """A feature worth telling the product's users about, with the date it arrived.

    Written by hand when a release is cut, at the level of "ZTP for Cisco switches": one list for the whole
    product (`content/highlights.md`), not per package. `components` can name the releases a highlight came in
    so that the page leads to their details; the product's own highlights leave it empty.
    """

    id: str
    date: datetime.date
    title: str
    description: str | None = None
    components: list[HighlightComponent] = []


class ComponentChangelog(BaseModel):
    """The compiled changelog of one component: the file format."""

    schema_version: int = SCHEMA_VERSION
    #: The distribution name, which is unique on any package index: "acex", "acex-driver-cisco-ioscli".
    component: str
    #: Shown to users: "ACEX backend", "Cisco IOS CLI driver".
    name: str
    #: Only for files outside the product (ACEX_CHANGELOG_EXTRA_DIR). Packages are always the product.
    section: SectionInfo | None = None
    releases: list[ChangelogRelease] = []
    coming: list[ComingFeature] = []
    highlights: list[Highlight] = []

    @field_validator("highlights", mode="before")
    @classmethod
    def _keep_the_good_highlights(cls, value):
        """A highlight that cannot be read is dropped (and logged); it must not take the releases with it."""
        if not isinstance(value, list):
            return []
        kept = []
        for item in value:
            try:
                kept.append(Highlight.model_validate(item))
            except ValidationError as exc:
                logger.warning(f"highlight skipped: {exc.error_count()} problem(s) in {str(item)[:80]}")
        return kept


# --- GET /changelog ---------------------------------------------------------


class ChangelogComponent(BaseModel):
    id: str
    name: str
    source: SourceKind


class ComponentRelease(ChangelogRelease):
    component: str


class ChangelogSection(BaseModel):
    id: str
    name: str
    components: list[ChangelogComponent]
    #: Newest first across the section's components; unreleased (version null) before everything.
    releases: list[ComponentRelease]
    coming: list[ComingFeature]


class ChangelogResponse(BaseModel):
    schema_version: int = SCHEMA_VERSION
    generated_at: datetime.datetime
    #: The product's highlights across its components, newest first.
    highlights: list[Highlight] = []
    #: The product first, then any deployment-specific sections by name.
    sections: list[ChangelogSection]
