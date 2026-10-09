"""Tests for worker startup via respx mocks."""

from __future__ import annotations

import json

import pytest
import respx
from acex_worker.main import JOB_TYPES, StartupError, start
from httpx import Response

BASE = "http://test"
API = f"{BASE}/api/v1"

CONNECTION = {
    "broker": {"host": "rabbitmq", "port": 5672, "vhost": "/", "user": "acex", "password": "pw"},
    "queues": [{"name": "acex.ztp", "durable": True}],
}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("ACEX_BASE_URL", BASE)
    for name in ("ACEX_CLIENT_ID", "ACEX_CLIENT_SECRET", "ACEX_ISSUER_URL", "ACEX_VERIFY_SSL"):
        monkeypatch.delenv(name, raising=False)


@respx.mock
def test_start_asks_for_the_queues_of_its_job_types():
    respx.get(f"{API}/auth/config").mock(return_value=Response(200, json={"enabled": False}))
    route = respx.post(f"{API}/workers/connect").mock(return_value=Response(200, json=CONNECTION))

    connection = start()

    assert json.loads(route.calls[0].request.content) == {"job_types": JOB_TYPES}
    assert connection.broker.host == "rabbitmq"
    assert [queue.name for queue in connection.queues] == ["acex.ztp"]


@respx.mock
def test_start_logs_in_with_client_credentials(monkeypatch):
    monkeypatch.setenv("ACEX_CLIENT_SECRET", "secret")
    respx.get(f"{API}/auth/config").mock(
        return_value=Response(200, json={"enabled": True, "authority": "http://idp", "client_id": "acex-worker"})
    )
    respx.get("http://idp/.well-known/openid-configuration").mock(
        return_value=Response(200, json={"token_endpoint": "http://idp/token"})
    )
    respx.post("http://idp/token").mock(return_value=Response(200, json={"access_token": "tok", "expires_in": 300}))
    route = respx.post(f"{API}/workers/connect").mock(return_value=Response(200, json=CONNECTION))

    start()

    assert route.calls[0].request.headers["Authorization"] == "Bearer tok"


@respx.mock
def test_start_refuses_browser_login_without_a_secret():
    respx.get(f"{API}/auth/config").mock(
        return_value=Response(200, json={"enabled": True, "authority": "http://idp", "client_id": "acex"})
    )
    respx.get("http://idp/.well-known/openid-configuration").mock(
        return_value=Response(
            200, json={"authorization_endpoint": "http://idp/auth", "token_endpoint": "http://idp/token"}
        )
    )
    connect = respx.post(f"{API}/workers/connect")

    with pytest.raises(StartupError, match="ACEX_CLIENT_SECRET"):
        start()

    assert not connect.called
