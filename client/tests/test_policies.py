"""Tests for the policies namespace via respx mocks."""

from __future__ import annotations

import json

import pytest
import respx
from acex_client.auth import NullAuthProvider
from acex_client.http import RestClient
from acex_client.resources.policies import PoliciesNamespace
from acex_devkit.models.policy import SoftwarePolicyCreate, SoftwarePolicyUpdate
from httpx import Response

API = "http://test/api/v1"

RULE = {
    "id": 1,
    "vendor": "cisco",
    "hardware_model": "C9300-24T",
    "os": "cisco_iosxe",
    "os_version": "17.9.4a",
    "golden": True,
    "updated_by": "alice",
    "updated_at": None,
}


@pytest.fixture
def policies():
    rest = RestClient(API, NullAuthProvider(), timeout=5.0)
    try:
        yield PoliciesNamespace(rest)
    finally:
        rest.close()


@respx.mock
def test_query_lists_the_approved_versions(policies):
    respx.get(f"{API}/policies/software").mock(return_value=Response(200, json=[RULE]))
    [version] = policies.software.query()
    assert (version.os_version, version.golden) == ("17.9.4a", True)


@respx.mock
def test_create_sends_the_version(policies):
    route = respx.post(f"{API}/policies/software").mock(return_value=Response(201, json=RULE))
    payload = SoftwarePolicyCreate(
        vendor="cisco", hardware_model="C9300-24T", os="cisco_iosxe", os_version="17.9.4a", golden=True
    )
    assert policies.software.create(payload=payload).id == 1
    assert json.loads(route.calls[0].request.content)["golden"] is True


@respx.mock
def test_update_sends_only_the_fields_set(policies):
    route = respx.patch(f"{API}/policies/software/1").mock(return_value=Response(200, json=RULE))
    policies.software.update(id=1, payload=SoftwarePolicyUpdate(golden=False))
    assert json.loads(route.calls[0].request.content) == {"golden": False}


@respx.mock
def test_versions_asks_for_the_versions_in_use(policies):
    route = respx.get(f"{API}/policies/software/versions").mock(
        return_value=Response(200, json=[{"os_version": "17.9.4a", "assets": 2}])
    )
    [version] = policies.software.versions(vendor="cisco", os="cisco_iosxe", hardware_model="C9300-24T")
    assert (version.os_version, version.assets) == ("17.9.4a", 2)
    params = dict(route.calls[0].request.url.params)
    assert params == {"vendor": "cisco", "os": "cisco_iosxe", "hardware_model": "C9300-24T"}
