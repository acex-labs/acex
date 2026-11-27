"""Git repositories that ConfigMaps are read from: how one is added, changed and shown, and how a file is sent to
one as a merge request.

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


def _python_file_in_the_repository(path: str) -> str:
    path = path.strip()
    pure = PurePosixPath(path)
    if not path or pure.is_absolute() or ".." in pure.parts or "\\" in path or not path.isprintable():
        raise ValueError("path must be a file in the repository, without .. or a leading /")
    if pure.parts[0] == ".git":
        raise ValueError("path must not be inside .git")
    if pure.suffix != ".py" or not pure.stem:
        raise ValueError("path must name a .py file: ConfigMaps are read from Python files only")
    return pure.as_posix()


def _site(site: str | None) -> str | None:
    """A site name without the spaces around it; empty means no site."""
    if site is None:
        return None
    return site.strip() or None


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
    #: Set: the ConfigMaps of this repository apply to the logical nodes of this site only, whatever their filters
    #: say, so each site can have a repository of its own that cannot reach another site.
    site: str | None = None
    #: A `token` credential whose token is the secret that the git host sends with its webhook
    #: (`POST /api/v1/git_repositories/{id}/webhook`), so a push to the branch syncs the repository at once.
    webhook_credential_id: int | None = None
    #: A `token` credential whose token may write to the repository through the git host's API, so that a file can be
    #: sent to it as a merge request (`POST /api/v1/git_repositories/{id}/merge_requests`). Kept apart from
    #: `credential_id`, which only needs to read. GitLab only.
    merge_request_credential_id: int | None = None

    @field_validator("site")
    @classmethod
    def _check_site(cls, site: str | None) -> str | None:
        return _site(site)

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
    """Changes to a repository: only the fields sent are changed. `credential_id`, `username`, `ca_certificate`,
    `site`, `webhook_credential_id` and `merge_request_credential_id` are cleared by sending null; the other fields
    keep their value when sent as null."""

    name: str | None = Field(None, min_length=1)
    url: str | None = None
    branch: str | None = Field(None, min_length=1)
    path: str | None = None
    auth_method: GitAuthMethod | None = None
    credential_id: int | None = None
    username: str | None = None
    ca_certificate: str | None = None
    enabled: bool | None = None
    site: str | None = None
    webhook_credential_id: int | None = None
    merge_request_credential_id: int | None = None

    @field_validator("site")
    @classmethod
    def _check_site(cls, site: str | None) -> str | None:
        return _site(site)

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
    #: The only site whose logical nodes the repository's ConfigMaps apply to; empty: any, as their filters say.
    site: str | None = None
    #: The credential that holds the secret of the repository's webhook; empty: no webhook.
    webhook_credential_id: int | None = None
    #: The credential that merge requests are sent with; empty: none can be sent to this repository.
    merge_request_credential_id: int | None = None
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


class GitRepositoryTree(BaseModel):
    """The directories and files on the branch a repository follows, as its git host lists them now."""

    branch: str
    directories: list[str] = []
    files: list[str] = []
    #: True when the repository holds more than was listed.
    truncated: bool = False


class MergeRequestCreate(BaseModel):
    """A Python file to send to a repository as a merge request into the branch it follows."""

    #: Where the file goes, from the root of the repository, for example `got/ntp.py`. A directory that does
    #: not exist yet is made.
    path: str
    content: str = Field(min_length=1, max_length=1_000_000)
    #: The title of the merge request and the message of its commit.
    title: str = Field(min_length=1, max_length=255)
    #: Text for the merge request, as Markdown.
    description: str | None = Field(None, max_length=20_000)
    #: Change the file when the path already holds one. Left false, such a request is refused.
    replace: bool = False

    @field_validator("path")
    @classmethod
    def _check_path(cls, path: str) -> str:
        return _python_file_in_the_repository(path)

    @field_validator("title")
    @classmethod
    def _check_title(cls, title: str) -> str:
        title = title.strip()
        if not title or "\n" in title:
            raise ValueError("title must be one line of text")
        return title


class MergeRequestResponse(BaseModel):
    """A merge request that was opened on the git host."""

    #: Where it is read and merged, on the git host.
    url: str
    #: Its number in the project.
    number: int
    #: The new branch that holds the file, and the branch the merge request asks to merge it into.
    source_branch: str
    target_branch: str
    path: str
