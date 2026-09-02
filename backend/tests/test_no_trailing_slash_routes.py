"""Regression test: no API route may be registered with a trailing slash.

Historical context: collection endpoints were mounted as e.g.
``/api/v1/inventory/sites/`` while first-party clients called them without the
slash. That forced a 307 on every list call, and behind a TLS-terminating
proxy the redirect Location came back with an ``http://`` scheme — clients
like httpx then strip the Authorization header on the cross-origin redirect
and the call dies with 401 "Not authenticated".

Canonical form is now slash-free everywhere (FastAPI's ``redirect_slashes``
still serves legacy slash-form URLs via 307). This test keeps new routers
from reintroducing the trailing-slash form at the source.
"""

import re
from pathlib import Path

from acex.plugins.adaptors.adapter_base import AdapterBase

ROUTERS_DIR = Path(__file__).resolve().parent.parent / "src" / "acex" / "api" / "routers"

_ROUTE_LITERAL = re.compile(r'(?:add_api_route\(|@router\.(?:get|post|put|patch|delete|head)\()\s*f?"([^"]*)"')


def test_adapter_base_paths_are_slash_free():
    adapter = AdapterBase(None)
    for capability in adapter.capabilities:
        path = adapter.path(capability)
        assert not path.endswith("/"), f"{capability} -> {path!r} ends with '/'"


def test_static_routers_register_no_trailing_slash_paths():
    offenders: dict[str, list[str]] = {}
    for file in sorted(ROUTERS_DIR.glob("*.py")):
        if file.name == "__init__.py":
            continue
        for match in _ROUTE_LITERAL.finditer(file.read_text()):
            path = match.group(1)
            if path.endswith("/"):
                offenders.setdefault(file.name, []).append(path)
    assert not offenders, f"Routes with trailing slash (use the plain form): {offenders}"
