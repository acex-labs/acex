"""Git repositories that ConfigMaps are read from: how one is added, changed and shown.

A repository is added with its HTTPS URL, the branch and the directory that holds the ConfigMaps, and, unless the
host lets anyone read it, a `token` credential. The URL never holds a secret: the token is read from the credential
when git runs.
"""

from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from acex_devkit.models.base import PersistedResponse


class GitAuthMethod(StrEnum):
    """How the backend signs in to a repository."""

    #: A host that lets anyone read the repository.
    HTTPS_ANONYMOUS = "https_anonymous"
    #: A personal access token, kept in a `token` credential.
    HTTPS_TOKEN = "https_token"


#: The type of credential each method signs in with; None where it needs none.
GIT_AUTH_CREDENTIAL_TYPES: dict[GitAuthMethod, str | None] = {
    GitAuthMethod.HTTPS_ANONYMOUS: None,
    GitAuthMethod.HTTPS_TOKEN: "token",
}

_PEM_CERTIFICATE = "-----BEGIN CERTIFICATE-----"


def _https_url(url: str) -> str:
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("url must be an https:// URL")
    if parts.username or parts.password:
        raise ValueError("url must not hold a user name or a password: give the repository a credential")
    return url


def _directory_in_the_repository(path: str) -> str:
    path = path.strip()
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError("path must be a directory in the repository, without .. or a leading /")
    return "" if path in ("", ".") else pure.as_posix()


def _pem(ca_certificate: str | None) -> str | None:
    if ca_certificate and _PEM_CERTIFICATE not in ca_certificate:
        raise ValueError(f"ca_certificate must be one or more PEM certificates, each starting with {_PEM_CERTIFICATE}")
    return ca_certificate


class GitRepositoryCreate(BaseModel):
    """A repository to read ConfigMaps from. It is synced as soon as it is added."""

    name: str = Field(min_length=1)
    #: An https:// URL without a user name or a password.
    url: str
    branch: str = Field("main", min_length=1)
    #: The directory in the repository that holds the ConfigMaps; empty for its root.
    path: str = ""
    auth_method: GitAuthMethod = GitAuthMethod.HTTPS_TOKEN
    #: The `token` credential to sign in with. Not used by `https_anonymous`.
    credential_id: int | None = None
    #: Most hosts take any user name with a token; Bitbucket wants the account's. Empty: `x-access-token`.
    username: str | None = None
    #: PEM certificates to trust for the host besides the system's, for a host that an internal CA signed.
    ca_certificate: str | None = None
    enabled: bool = True

    @field_validator("url")
    @classmethod
    def _check_url(cls, url: str) -> str:
        return _https_url(url)

    @field_validator("path")
    @classmethod
    def _check_path(cls, path: str) -> str:
        return _directory_in_the_repository(path)

    @field_validator("ca_certificate")
    @classmethod
    def _check_ca_certificate(cls, ca_certificate: str | None) -> str | None:
        return _pem(ca_certificate)


class GitRepositoryUpdate(BaseModel):
    """Changes to a repository: only the fields sent are changed. `credential_id`, `username` and
    `ca_certificate` are cleared by sending null; the other fields keep their value when sent as null."""

    name: str | None = Field(None, min_length=1)
    url: str | None = None
    branch: str | None = Field(None, min_length=1)
    path: str | None = None
    auth_method: GitAuthMethod | None = None
    credential_id: int | None = None
    username: str | None = None
    ca_certificate: str | None = None
    enabled: bool | None = None

    @field_validator("url")
    @classmethod
    def _check_url(cls, url: str | None) -> str | None:
        return None if url is None else _https_url(url)

    @field_validator("path")
    @classmethod
    def _check_path(cls, path: str | None) -> str | None:
        return None if path is None else _directory_in_the_repository(path)

    @field_validator("ca_certificate")
    @classmethod
    def _check_ca_certificate(cls, ca_certificate: str | None) -> str | None:
        return _pem(ca_certificate)


class GitRepositoryResponse(PersistedResponse):
    """A repository and how its last sync went."""

    name: str
    url: str
    branch: str
    path: str
    auth_method: GitAuthMethod
    credential_id: int | None = None
    username: str | None = None
    ca_certificate: str | None = None
    enabled: bool
    #: The commit that is loaded, when the branch was last asked about and when a commit was last loaded.
    commit: str | None = None
    last_checked_at: datetime | None = None
    last_synced_at: datetime | None = None
    #: Why the last sync failed; empty when it did not.
    last_error: str | None = None
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime
    #: The ConfigMaps loaded from the repository by the process that answered, as `file.py:variable`.
    config_maps: list[str] = []
