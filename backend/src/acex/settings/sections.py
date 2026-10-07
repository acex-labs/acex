"""Core sections: database, serving, auth, CORS and credential storage."""

from typing import Annotated, Any

from acex.settings.base import Section
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import NoDecode


class DatabaseSettings(Section, env_prefix="DB_"):
    """Database the engine persists to. Migrations run on startup."""

    backend: str = "postgresql"
    name: str = "ace"
    user: str = "postgres"
    password: SecretStr = SecretStr("")
    host: str = "localhost"
    port: int = 5432


class ServerSettings(Section, env_prefix="ACEX_"):
    """Where the API is served when started through `acex-api`."""

    host: str = "0.0.0.0"
    port: int = 8080
    #: Restart on source changes. Dev mode turns this on unless told otherwise.
    reload: bool = False


class OidcSettings(Section, env_prefix="OIDC_"):
    """OIDC provider that issues the bearer tokens the API accepts.

    Without an issuer every endpoint is open, so it is required outside dev mode.
    """

    issuer_url: str | None = None
    audience: str = "acex"
    jwks_ttl: int = 3600
    verify_ssl: bool = True


# An explicitly empty ACEX_CORS_ALLOWED_ORIGINS means "no origins", so here
# empty values are not ignored.
class CorsSettings(Section, env_prefix="ACEX_CORS_", env_ignore_empty=False):
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


class VaultSettings(Section, env_prefix="VAULT_"):
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


class CredentialSettings(Section, env_prefix="ACEX_"):
    """Encryption of stored device credentials."""

    encryption_key: SecretStr | None = None
    #: Read from VAULT_*, not ACEX_VAULT__*: Vault's own variable names.
    vault: VaultSettings = Field(default_factory=VaultSettings)
