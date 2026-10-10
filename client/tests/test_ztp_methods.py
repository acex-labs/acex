"""Tests for the ztp_methods resource via respx mocks."""

from __future__ import annotations

import json

import pytest
import respx
from acex_client.auth import NullAuthProvider
from acex_client.exceptions import AcexValidationError
from acex_client.http import RestClient
from acex_client.resources.ztp_methods import ZtpMethods
from acex_devkit.models.ztp import ZtpMethod, ZtpMethodUpdate
from httpx import Response

API = "http://test/api/v1"

METHOD = {
    "method": "cisco_iosxe_python",
    "label": "Cisco IOS XE — Python",
    "description": "The device downloads ztp.py over HTTP and runs it in guestshell.",
    "ned": "CiscoIOSCLIDriver",
    "updated_by": "alice",
    "updated_at": None,
}


@pytest.fixture
def methods():
    rest = RestClient(API, NullAuthProvider(), timeout=5.0)
    try:
        yield ZtpMethods(rest)
    finally:
        rest.close()


@respx.mock
def test_query_lists_every_method(methods):
    respx.get(f"{API}/ztp_methods").mock(return_value=Response(200, json=[METHOD]))

    assert [method.ned for method in methods.query()] == ["CiscoIOSCLIDriver"]


@respx.mock
def test_get_returns_the_ned_chosen_for_a_method(methods):
    respx.get(f"{API}/ztp_methods/cisco_iosxe_python").mock(return_value=Response(200, json=METHOD))

    method = methods.get(method=ZtpMethod.cisco_iosxe_python)

    assert method.method == ZtpMethod.cisco_iosxe_python
    assert method.ned == "CiscoIOSCLIDriver"


@respx.mock
def test_update_sends_the_chosen_ned(methods):
    route = respx.put(f"{API}/ztp_methods/cisco_iosxe_python").mock(return_value=Response(200, json=METHOD))

    methods.update(method=ZtpMethod.cisco_iosxe_python, payload=ZtpMethodUpdate(ned="CiscoIOSCLIDriver"))

    assert json.loads(route.calls[0].request.content) == {"ned": "CiscoIOSCLIDriver"}


@respx.mock
def test_update_with_an_unknown_ned_raises(methods):
    respx.put(f"{API}/ztp_methods/cisco_iosxe_python").mock(
        return_value=Response(422, json={"detail": "No NED named 'Nope' is installed."})
    )

    with pytest.raises(AcexValidationError):
        methods.update(method=ZtpMethod.cisco_iosxe_python, payload=ZtpMethodUpdate(ned="Nope"))
