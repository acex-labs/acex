"""Core sections: database, serving, auth, CORS, credential storage and messaging."""

from typing import Annotated, Any
from urllib.parse import quote

from acex.settings.section import Section
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import NoDecode


class DatabaseSettings(Section, name="db"):
    """Database the engine persists to. Migrations run on startup."""

    backend: str = "postgresql"
    name: str = "ace"
    user: str = "postgres"
    password: SecretStr = SecretStr("")
    host: str = "localhost"
    port: int = 5432


class ServerSettings(Section, name="server"):
    """Where the API is served when started through `acex-api`."""

    host: str = "0.0.0.0"
    port: int = 8080
    #: Restart on source changes. Dev mode turns this on unless told otherwise.
    reload: bool = False
    #: Proxies whose X-Forwarded-For is trusted for the client's address: a
    #: comma-separated list of addresses or networks, or "*". Unset trusts
    #: only localhost. "*" is safe only when nothing but the proxy can reach
    #: the API, since anyone else could then claim any address.
    forwarded_allow_ips: str | None = None


class OidcSettings(Section, name="oidc"):
    """OIDC provider that issues the bearer tokens the API accepts.

    Without an issuer every endpoint is open, so it is required outside dev mode.
    """

    issuer_url: str | None = None
    audience: str = "acex"
    jwks_ttl: int = 3600
    verify_ssl: bool = True


# An explicitly empty ACEX_CORS_ALLOWED_ORIGINS means "no origins", so here
# empty values are not ignored.
class CorsSettings(Section, name="cors", env_ignore_empty=False):
    """Browser origins allowed to make cross-origin calls.

    Empty by default: no CORS headers are sent at all, so a browser will only
    let the API be called from its own origin. Name the frontend here when it
    is served from somewhere else. "*" is rejected outside dev mode — the API
    sends credentials, and a wildcard tells Starlette to echo back whatever
    Origin asks, which trusts every site on the web.
    """

    #: Comma-separated in the environment, e.g. "https://acex.example.net".
    allowed_origins: Annotated[list[str], NoDecode] = []

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


class VaultSettings(Section, name="credentials.vault"):
    """HashiCorp Vault for credential storage.

    Used when an address and either a token or an AppRole (role + secret id)
    are set.
    """

    addr: str | None = None
    token: SecretStr | None = None
    role_id: str | None = None
    secret_id: SecretStr | None = None
    verify: bool = True

    @property
    def configured(self) -> bool:
        return bool(self.addr and (self.token or (self.role_id and self.secret_id)))


class CredentialSettings(Section, name="credentials"):
    """Encryption of stored device credentials."""

    encryption_key: SecretStr | None = None
    vault: VaultSettings = Field(default_factory=VaultSettings)


class RabbitMQSettings(Section, name="rabbitmq"):
    """RabbitMQ broker the backend publishes jobs to for workers to run.

    Off until a host is set. Workers are handed the same connection. The queues
    are declared in code, so the user needs configure, write and read
    permissions on the vhost.
    """

    host: str | None = None
    #: The AMQP port, not the management UI's 15672.
    port: int = 5672
    vhost: str = "/"
    user: str | None = None
    password: SecretStr | None = None

    @property
    def configured(self) -> bool:
        return self.host is not None

    @property
    def url(self) -> str:
        """The AMQP URL for client libraries, with every part quoted (a "/" vhost is %2F)."""
        credentials = ""
        if self.user is not None:
            credentials = quote(self.user, safe="")
            if self.password is not None:
                credentials += ":" + quote(self.password.get_secret_value(), safe="")
            credentials += "@"
        return f"amqp://{credentials}{self.host}:{self.port}/{quote(self.vhost, safe='')}"
