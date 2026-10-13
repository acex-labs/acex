"""What the changelog endpoint answers, and the file format behind it.

`ComponentChangelog` is the compiled `changelog.json` that every component
ships inside its package (built by acex.changelog.tool). The same shape, with
a `section`, is what a deployment drops into ACEX_CHANGELOG_EXTRA_DIR for
notes that must never be part of the product. The API response below is an
aggregate of those files.
"""

import datetime
from enum import StrEnum

from pydantic import BaseModel

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
    entries: list[ChangelogEntry] = []


class ComingStatus(StrEnum):
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
    refs: list[Reference] = []


class SectionInfo(BaseModel):
    """Which list the notes belong to. The product is one section; a deployment's own notes are another."""

    id: str
    name: str


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
    #: The product first, then any deployment-specific sections by name.
    sections: list[ChangelogSection]
