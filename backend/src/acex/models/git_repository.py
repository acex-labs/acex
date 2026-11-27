from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class GitRepositoryRow(SQLModel, table=True):
    """A git repository the backend reads ConfigMaps from, and how its last sync went."""

    __tablename__ = "git_repository"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    url: str
    branch: str = "main"
    path: str = ""
    auth_method: str
    #: Not a foreign key: deleting a credential must not be blocked by a repository using it. A sync
    #: then fails and says so.
    credential_id: int | None = None
    username: str | None = None
    #: PEM certificates to trust for the host, besides the system's.
    ca_certificate: str | None = None
    enabled: bool = True
    #: Set: the repository's ConfigMaps apply to the logical nodes of this site only.
    site: str | None = None
    #: A `token` credential whose token is the secret of the repository's webhook. Not a foreign key, like the
    #: credential above. Empty: the repository has no webhook.
    webhook_credential_id: int | None = None
    #: A `token` credential that merge requests are sent with, through the git host's API. Not a foreign key
    #: either. Empty: none can be sent to the repository.
    merge_request_credential_id: int | None = None

    commit: str | None = None
    last_checked_at: datetime | None = None
    last_synced_at: datetime | None = None
    last_error: str | None = None

    created_by: str
    updated_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


__all__ = ["GitRepositoryRow"]
