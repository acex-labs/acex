"""Tests for config_components, neds, ai, system namespaces via respx mocks."""

from __future__ import annotations

import pytest
import respx
from acex_client.auth import NullAuthProvider
from acex_client.http import RestClient
from acex_client.resources.ai import Ai
from acex_client.resources.config_components import ConfigComponents
from acex_client.resources.neds import Neds
from acex_client.resources.system import SystemNamespace
from httpx import Response


@pytest.fixture
def rest():
    r = RestClient("http://test/api/v1", NullAuthProvider(), timeout=5.0)
    try:
        yield r
    finally:
        r.close()


# ---------------------------------------------------------------------------
# Config components
# ---------------------------------------------------------------------------


@respx.mock
def test_config_components_list(rest):
    respx.get("http://test/api/v1/config_components").mock(
        return_value=Response(
            200,
            json=[
                {
                    "type": "HostName",
                    "class_name": "HostName",
                    "module": "acex.configuration.components",
                    "path_template": "system.config",
                    "fields": [],
                },
            ],
        )
    )
    result = ConfigComponents(rest).catalog()
    assert len(result) == 1
    assert result[0].type == "HostName"


@respx.mock
def test_config_components_drivers(rest):
    respx.get("http://test/api/v1/config_components/drivers").mock(
        return_value=Response(
            200,
            json=[
                {
                    "ned_id": "cisco-ios",
                    "name": "Cisco IOS",
                    "package_name": "acex-driver-cisco-ioscli",
                    "version": "1.0.0",
                    "description": "Cisco IOS driver",
                },
            ],
        )
    )
    result = ConfigComponents(rest).drivers()
    assert len(result) == 1
    assert result[0].ned_id == "cisco-ios"


@respx.mock
def test_config_components_reconcile(rest):
    respx.post("http://test/api/v1/config_components/reconcile/1").mock(
        return_value=Response(200, json={"configmap": "# generated ConfigMap"})
    )
    from acex_devkit.models.config_components import ReconcileMode, ReconcileRequest

    result = ConfigComponents(rest).reconcile(
        node_instance_id=1,
        payload=ReconcileRequest(mode=ReconcileMode.full),
    )
    assert result.configmap.startswith("# generated")


@respx.mock
def test_config_components_translate(rest):
    respx.post("http://test/api/v1/config_components/translate").mock(
        return_value=Response(200, json={"configmap": "# ConfigMap"})
    )
    from acex_devkit.models.config_components import TranslateRequest

    result = ConfigComponents(rest).translate(payload=TranslateRequest(ned_id="cisco-ios", config="hostname R1\n"))
    assert result.configmap.startswith("#")


# ---------------------------------------------------------------------------
# Neds
# ---------------------------------------------------------------------------


@respx.mock
def test_neds_list_and_get(rest):
    respx.get("http://test/api/v1/neds").mock(
        return_value=Response(
            200,
            json=[
                {
                    "name": "cisco-ios",
                    "package_name": "acex-driver-cisco-ioscli",
                    "version": "1.0.0",
                    "description": "Cisco IOS",
                    "filename": "acex_driver_cisco_ioscli-1.0.0-py3-none-any.whl",
                },
            ],
        )
    )
    respx.get("http://test/api/v1/neds/cisco-ios").mock(
        return_value=Response(
            200,
            json={
                "name": "cisco-ios",
                "package_name": "acex-driver-cisco-ioscli",
                "version": "1.0.0",
                "description": "Cisco IOS",
                "filename": "acex_driver_cisco_ioscli-1.0.0-py3-none-any.whl",
            },
        )
    )
    listed = Neds(rest).query()
    assert len(listed) == 1
    assert listed[0].name == "cisco-ios"

    got = Neds(rest).get(ned_id="cisco-ios")
    assert got.name == "cisco-ios"


@respx.mock
def test_neds_download(rest):
    respx.get("http://test/api/v1/neds/download/driver.whl").mock(
        return_value=Response(200, content=b"binary wheel bytes", headers={"content-type": "application/octet-stream"})
    )
    data = Neds(rest).download(filename="driver.whl")
    assert data == b"binary wheel bytes"


# ---------------------------------------------------------------------------
# AI (SSE)
# ---------------------------------------------------------------------------


@respx.mock
def test_ai_ask_streams(rest):
    body = b"event: token\ndata: Hello\nevent: token\ndata:  world\n"
    respx.post("http://test/api/v1/ai_ops/ai/ask").mock(
        return_value=Response(200, content=body, headers={"content-type": "text/event-stream"})
    )
    from acex_devkit.models.ai_ops import AiAskRequest

    ai = Ai(rest)
    chunks = list(ai.ask(payload=AiAskRequest(question="hello")))
    assert chunks == ["Hello", "world"]


# ---------------------------------------------------------------------------
# System (auth_config, health aliases)
# ---------------------------------------------------------------------------


@respx.mock
def test_system_auth_config(rest):
    respx.get("http://test/api/v1/auth/config").mock(
        return_value=Response(200, json={"enabled": True, "authority": "https://idp", "client_id": "acex"})
    )
    result = SystemNamespace(rest).auth_config()
    assert result.enabled is True
    assert result.authority == "https://idp"


@respx.mock
def test_system_health_node(rest):
    respx.get("http://test/api/v1/health/node_instance/1").mock(
        return_value=Response(
            200,
            json={
                "total_desired": 5,
                "total_observed": 5,
                "compliant_count": 5,
                "compliance_percentage": 100.0,
            },
        )
    )
    result = SystemNamespace(rest).health_node(node_instance_id=1)
    assert result.compliance_percentage == 100.0
