"""Smoke test — `Acex` can be constructed with an injected NullAuthProvider,
and the public namespace attributes are populated after construction."""

from acex_client import Acex
from acex_client.auth import NullAuthProvider


def test_smoke():
    # No network call: NullAuthProvider avoids the /auth/config probe, and
    # the optional HEAD /ai_ops/ai/ask/ probe will fail silently (ai=None).
    with Acex(base_url="http://test.invalid/", auth=NullAuthProvider()) as client:
        assert client.api_url == "http://test.invalid/api/v1"
        assert client.inventory is not None
        assert client.observability is not None
        assert client.operations is not None
        assert client.config_components is not None
        assert client.neds is not None
        assert client.system is not None
        # ai probe returns None because connection fails (network unreachable).
        assert client.ai is None
