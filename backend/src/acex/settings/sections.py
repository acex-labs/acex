"""Core sections: database, serving, auth, CORS, credential storage and messaging."""

from typing import Annotated, Any
from urllib.parse import quote

from acex.settings.section import Section
from acex_devkit.messaging import amqp_ssl_options
from pydantic import Field, SecretStr, field_validator, model_validator
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

    Off until a host is set. Workers are handed the same connection unless the ``worker_*`` settings say that they
    reach the broker another way. The queues are declared in code, so the user needs configure, write and read
    permissions on the vhost.
    """

    host: str | None = None
    #: The AMQP port, not the management UI's 15672.
    port: int = 5672
    vhost: str = "/"
    user: str | None = None
    password: SecretStr | None = None
    #: Connect to the broker with TLS (amqps://), always verifying its certificate.
    tls: bool = False
    #: CA bundle the broker's certificate is checked against. Unset: the system's trusted roots.
    tls_ca_file: str | None = None
    #: The backend's own client certificate and key, for a broker that requires one. Set both or neither.
    tls_cert_file: str | None = None
    tls_key_file: str | None = None
    #: What workers are handed instead of the backend's own host, port and TLS setting, when they do not reach the
    #: broker the way the backend does: the backend inside the cluster on the plain port, a worker in a customer's
    #: network through a TLS endpoint. Unset: the same as the backend.
    worker_host: str | None = None
    worker_port: int | None = None
    worker_tls: bool | None = None

    @model_validator(mode="after")
    def _client_certificate_is_a_pair(self) -> "RabbitMQSettings":
        if (self.tls_cert_file is None) != (self.tls_key_file is None):
            raise ValueError("ACEX_RABBITMQ_TLS_CERT_FILE and ACEX_RABBITMQ_TLS_KEY_FILE must be set together")
        return self

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
        scheme = "amqps" if self.tls else "amqp"
        return f"{scheme}://{credentials}{self.host}:{self.port}/{quote(self.vhost, safe='')}"

    @property
    def ssl_options(self) -> dict[str, Any] | None:
        """Celery's ``broker_use_ssl`` for the backend's own connection, or None without TLS."""
        return amqp_ssl_options(
            tls=self.tls, ca_file=self.tls_ca_file, cert_file=self.tls_cert_file, key_file=self.tls_key_file
        )

    @property
    def worker_connection(self) -> tuple[str | None, int, bool]:
        """The host, port and TLS setting that workers are told to use."""
        return (
            self.worker_host or self.host,
            self.worker_port or self.port,
            self.tls if self.worker_tls is None else self.worker_tls,
        )


class ZtpSettings(Section, name="ztp"):
    """Zero touch provisioning."""

    #: A provisioning job queued longer than this is taken as lost: no worker picked it up.
    provision_queue_timeout_minutes: int = 10
    #: A provisioning job running longer than this is taken as lost: its worker stopped reporting.
    provision_run_timeout_minutes: int = 30


class GitSyncSettings(Section, name="git_sync"):
    """Git repositories that ConfigMaps are read from (set up under /api/v1/git_repositories)."""

    #: How often each repository is asked whether its branch has moved, in seconds.
    poll_interval_seconds: int = Field(default=1800, ge=60)
    #: Where repositories are checked out. Left unset, a directory under the system's temp
    #: directory; set it to a volume to keep the last checkout when a restart can't reach the host.
    checkout_dir: str | None = None
    #: How long one git command may run, in seconds.
    timeout_seconds: int = Field(default=120, ge=1)


class ChangelogSettings(Section, name="changelog"):
    """Release notes that belong to this deployment only.

    A directory of `changelog.json` files in the same format the packages
    use, each with a `section` of its own. They are shown apart from the
    product's notes and never ship with it. Mount it from a ConfigMap or
    write it from your own pipeline; see docs/guides/changelog.md.
    """

    extra_dir: str | None = None
