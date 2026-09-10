"""Runtime configuration for the ACE-X MCP server.

The server deliberately owns almost no configuration of its own: OIDC settings
are discovered from the backend at runtime (see auth.py) so that the backend
stays the single place authentication is configured.
"""

import os
from dataclasses import dataclass, field

#: Transport for the MCP protocol itself.
#:   "http"  — served over Streamable HTTP; inbound requests carry a bearer token.
#:   "stdio" — spawned by a local client (Claude Desktop et al) over a pipe. There
#:             is no inbound request to read a token from, so the process
#:             authenticates as the user via acex_client's own env/browser flow.
TRANSPORTS = ("http", "stdio")


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("false", "0", "no")


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class Settings:
    #: Backend base URL *without* the /api/v1 suffix — acex_client appends it.
    api_url: str = field(default_factory=lambda: os.environ.get("ACEX_API_URL", "http://localhost:8080"))
    verify_ssl: bool = field(default_factory=lambda: _flag("ACEX_VERIFY_SSL", True))

    transport: str = field(default_factory=lambda: os.environ.get("ACEX_MCP_TRANSPORT", "http"))
    host: str = field(default_factory=lambda: os.environ.get("ACEX_MCP_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _int("ACEX_MCP_PORT", 8000))
    path: str = field(default_factory=lambda: os.environ.get("ACEX_MCP_PATH", "/mcp"))

    #: Per-request timeout against the backend. Some endpoints compile a whole
    #: config tree, so this is generous — but never unbounded, which is what
    #: the previous implementation effectively had.
    request_timeout: float = field(default_factory=lambda: float(_int("ACEX_MCP_REQUEST_TIMEOUT", 60)))

    #: Hard ceiling on characters of config text returned by a single tool call.
    #: Beyond this the text is truncated with a marker telling the model to
    #: narrow the request with `section` instead of asking for more.
    max_config_chars: int = field(default_factory=lambda: _int("ACEX_MCP_MAX_CONFIG_CHARS", 24000))

    def __post_init__(self):
        if self.transport not in TRANSPORTS:
            raise ValueError(f"ACEX_MCP_TRANSPORT must be one of {TRANSPORTS}, got '{self.transport}'")
        self.api_url = self.api_url.rstrip("/")

    @property
    def is_stdio(self) -> bool:
        return self.transport == "stdio"


settings = Settings()
