"""Device OS version contract.

An OS version is reported by the device, not chosen by an integrator, so for
most platforms the set of valid values is open: a switch upgraded to a release
nobody declared must still be storable. What devkit fixes is which strings are
acceptable for a given OS, declared one of two ways:

* ``patterns`` - the regular expressions a version may match, one per spelling
  the platform uses. Name the groups ``major``, ``minor``, ``patch``, ``build``
  and ``qualifier`` and the version also becomes comparable, at no extra cost.
* ``versions`` - an explicit list, for a platform where the set really is
  closed and curated.

Declaring either is data, not code: see ``acex_devkit.os_versions``.

Normalized components, using the vendor spellings as examples:

===============  ======  ======  =====  =====  =========
raw              major   minor   patch  build  qualifier
===============  ======  ======  =====  =====  =========
17.9.4a              17       9      4   None  'a'
15.2(7)E3            15       2      7   None  'E3'
22.4R1.10            22       4      1     10  None
22.4R1-S2            22       4      1   None  'S2'
10.2.5               10       2      5   None  None
===============  ======  ======  =====  =====  =========
"""

import re
from functools import total_ordering
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator, model_validator

from acex_devkit.models.platform import OS

COMPONENTS = ("major", "minor", "patch", "build", "qualifier")


@total_ordering
class OsVersion(BaseModel):
    """A device OS version in normalized, comparable form."""

    raw: str = Field(min_length=1)
    major: int = Field(ge=0)
    minor: int = Field(ge=0)
    patch: int | None = Field(default=None, ge=0)
    build: int | None = Field(default=None, ge=0)
    qualifier: str | None = None

    @field_validator("qualifier")
    @classmethod
    def _qualifier_shape(cls, v: str | None) -> str | None:
        if v is not None and (not v or not v.isalnum()):
            raise ValueError("qualifier must be a non-empty alphanumeric tag")
        return v

    @property
    def sort_key(self) -> tuple:
        """Ordering key.

        A bare release sorts before its rebuilds (17.9.4 < 17.9.4a), and the
        qualifier outranks the build number: a Junos service release is later
        than any spin of the base release, so 22.4R1.10 < 22.4R1-S2.
        """
        return (self.major, self.minor, self.patch or 0, self.qualifier or "", self.build or 0)

    def __lt__(self, other: "OsVersion") -> bool:
        if not isinstance(other, OsVersion):
            return NotImplemented
        return self.sort_key < other.sort_key

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OsVersion):
            return NotImplemented
        return self.sort_key == other.sort_key

    def __hash__(self) -> int:
        return hash(self.sort_key)

    def __str__(self) -> str:
        return self.raw


class OsVersionScheme(BaseModel):
    """Declares which version strings are valid for one OS.

    Subclassing registers the scheme. Set ``patterns`` or ``versions``, not both.
    """

    os: OS
    patterns: list[str] | None = None
    versions: list[str] | None = None
    examples: list[str] = Field(default_factory=list)

    registry: ClassVar[dict[OS, "OsVersionScheme"]] = {}
    abstract: ClassVar[bool] = True

    def __init_subclass__(cls, abstract: bool = False, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.abstract = abstract

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        super().__pydantic_init_subclass__(**kwargs)
        if cls.abstract:
            return
        scheme = cls()
        OsVersionScheme.registry[scheme.os] = scheme

    @model_validator(mode="after")
    def _one_rule(self):
        if bool(self.patterns) == bool(self.versions):
            raise ValueError(f"{type(self).__name__}: declare exactly one of `patterns` or `versions`")
        for pattern in self.patterns or ():
            re.compile(pattern)  # fail loudly at declaration time, not at first use
        for example in self.examples:
            if not self.accepts(example):
                raise ValueError(f"{type(self).__name__}: declared example {example!r} does not satisfy the scheme")
        return self

    # --- validation -----------------------------------------------------
    def accepts(self, raw: str) -> bool:
        """Whether this OS may report ``raw`` as its version."""
        text = raw.strip()
        if self.versions is not None:
            return text in self.versions
        return any(re.fullmatch(p, text) for p in self.patterns)

    def check(self, raw: str) -> str:
        """Return ``raw`` stripped, or raise ``ValueError`` if the scheme rejects it."""
        text = raw.strip()
        if not self.accepts(text):
            raise ValueError(f"{text!r} is not a valid {self.os.value} version")
        return text

    # --- comparison -----------------------------------------------------
    def normalize(self, raw: str) -> OsVersion | None:
        """Build a comparable :class:`OsVersion` from the declared pattern's groups.

        Returns None for a scheme that declares no named components - the value
        is still valid, just not ordered.
        """
        text = self.check(raw)
        if self.versions is not None:
            return None
        match = next(m for m in (re.fullmatch(p, text) for p in self.patterns) if m)
        found = match.groupdict()
        if not found.get("major") or not found.get("minor"):
            return None
        fields = {k: found.get(k) for k in COMPONENTS}
        return OsVersion(
            raw=text,
            major=int(fields["major"]),
            minor=int(fields["minor"]),
            patch=int(fields["patch"]) if fields["patch"] else None,
            build=int(fields["build"]) if fields["build"] else None,
            qualifier=fields["qualifier"] or None,
        )

    # --- lookup ---------------------------------------------------------
    @classmethod
    def for_os(cls, os: OS) -> "OsVersionScheme | None":
        return cls.registry.get(os)
