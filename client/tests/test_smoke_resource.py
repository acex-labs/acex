"""Quick smoke of base.Resource CRUD via respx. Not part of the test suite yet —
verifies the end-to-end HTTP path before building real resource classes."""

from __future__ import annotations

import pytest
import respx
from acex_client.auth import NullAuthProvider
from acex_client.http import RestClient
from acex_client.resources.base import (
    CreateMixin,
    DeleteMixin,
    GetMixin,
    ListMixin,
    Resource,
    UpdateMixin,
)
from acex_devkit.models.site import SiteCreate, SiteResponse, SiteUpdate
from httpx import Response


class Sites(Resource, GetMixin, ListMixin, CreateMixin, UpdateMixin, DeleteMixin):
    path = "/inventory/sites"
    response_model = SiteResponse
    list_model = SiteResponse
    create_model = SiteCreate
    update_model = SiteUpdate


@pytest.fixture
def rest():
    r = RestClient("http://test/api/v1", NullAuthProvider(), timeout=5.0)
    try:
        yield r
    finally:
        r.close()


@respx.mock
def test_get_returns_live_instance(rest):
    respx.get("http://test/api/v1/inventory/sites/1").mock(
        return_value=Response(200, json={"id": 1, "name": "stockholm"})
    )
    sites = Sites(rest)
    site = sites.get(1)
    assert site.id == 1
    assert site.name == "stockholm"


@respx.mock
def test_get_404_raises(rest):
    from acex_client.exceptions import AcexNotFoundError

    respx.get("http://test/api/v1/inventory/sites/42").mock(return_value=Response(404))
    with pytest.raises(AcexNotFoundError):
        Sites(rest).get(42)


@respx.mock
def test_list_pagination(rest):
    respx.get("http://test/api/v1/inventory/sites").mock(
        return_value=Response(
            200,
            json={
                "items": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
                "total": 2,
                "limit": 100,
                "offset": 0,
            },
        )
    )
    result = Sites(rest).query()
    assert len(result) == 2
    assert result.items[0].name == "a"


@respx.mock
def test_create_validates_payload(rest):
    route = respx.post("http://test/api/v1/inventory/sites").mock(
        return_value=Response(201, json={"id": 7, "name": "new"})
    )
    site = Sites(rest).create(name="new")
    assert site.id == 7
    sent = route.calls[0].request.read()
    assert b"name" in sent


@respx.mock
def test_save_diffs_and_patches(rest):
    respx.get("http://test/api/v1/inventory/sites/1").mock(
        return_value=Response(200, json={"id": 1, "name": "old", "city": "SE"})
    )
    respx.patch("http://test/api/v1/inventory/sites/1").mock(
        return_value=Response(200, json={"id": 1, "name": "new", "city": "SE"})
    )
    sites = Sites(rest)
    site = sites.get(1)
    site.name = "new"
    site.save()


@respx.mock
def test_delete_404_raises(rest):
    from acex_client.exceptions import AcexNotFoundError

    respx.delete("http://test/api/v1/inventory/sites/1").mock(return_value=Response(404))
    with pytest.raises(AcexNotFoundError):
        Sites(rest).delete(1)
