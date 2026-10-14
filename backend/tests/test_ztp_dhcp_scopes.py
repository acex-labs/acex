"""ZTP DHCP scopes: IPv4 networks with a pool, a gateway and DNS, none overlapping another."""

from types import SimpleNamespace

import pytest
from acex.api import auth
from acex.api.routers.ztp_dhcp_scopes import create_router
from acex.ztp import ZtpDhcpScopeManager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

SCOPES = "/api/v1/ztp_dhcp_scopes"
SCOPE = {"network": "10.10.0.0/24", "pool_start": "10.10.0.100", "pool_end": "10.10.0.199", "gateway": "10.10.0.1"}


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


@pytest.fixture
def api():
    engine = SimpleNamespace(ztp_dhcp_scopes=ZtpDhcpScopeManager(_Db()))
    app = FastAPI()
    app.include_router(create_router(engine))
    app.dependency_overrides[auth.get_current_user] = lambda: {"preferred_username": "alice"}
    return TestClient(app)


def test_a_scope_is_kept_with_its_dns(api):
    response = api.post(SCOPES, json={**SCOPE, "dns_servers": ["10.0.0.53", "10.0.1.53"], "domain_name": " ztp.lab "})

    assert response.status_code == 201
    scope = api.get(SCOPES).json()[0]
    assert scope["dns_servers"] == ["10.0.0.53", "10.0.1.53"]
    assert (scope["domain_name"], scope["updated_by"]) == ("ztp.lab", "alice")


def test_scopes_are_listed_by_network(api):
    api.post(
        SCOPES,
        json={"network": "10.20.0.0/24", "pool_start": "10.20.0.10", "pool_end": "10.20.0.20", "gateway": "10.20.0.1"},
    )
    api.post(
        SCOPES,
        json={"network": "10.3.0.0/24", "pool_start": "10.3.0.10", "pool_end": "10.3.0.20", "gateway": "10.3.0.1"},
    )

    assert [s["network"] for s in api.get(SCOPES).json()] == ["10.3.0.0/24", "10.20.0.0/24"]


@pytest.mark.parametrize(
    "change",
    [
        {"network": "10.10.0.1/24"},
        {"network": "2001:db8::/64"},
        {"pool_start": "10.10.1.100"},
        {"pool_start": "10.10.0.200"},
        {"pool_end": "10.10.0.255"},
        {"gateway": "10.10.1.1"},
        {"gateway": "10.10.0.150"},
        {"dns_servers": ["dns.lab"]},
    ],
)
def test_a_scope_that_does_not_hold_together_is_refused(api, change):
    assert api.post(SCOPES, json={**SCOPE, **change}).status_code == 422


def test_overlapping_scopes_are_refused(api):
    api.post(SCOPES, json=SCOPE)

    overlapping = {
        "network": "10.10.0.0/16",
        "pool_start": "10.10.1.100",
        "pool_end": "10.10.1.199",
        "gateway": "10.10.1.1",
    }
    response = api.post(SCOPES, json=overlapping)

    assert response.status_code == 422
    assert "overlaps" in response.json()["detail"]


def test_an_update_is_checked_as_a_whole(api):
    id = api.post(SCOPES, json=SCOPE).json()["id"]

    assert api.patch(f"{SCOPES}/{id}", json={"gateway": "10.10.0.150"}).status_code == 422
    assert api.patch(f"{SCOPES}/{id}", json={"gateway": None}).status_code == 422


def test_an_update_keeps_what_is_left_out(api):
    id = api.post(SCOPES, json={**SCOPE, "dns_servers": ["10.0.0.53"]}).json()["id"]

    updated = api.patch(f"{SCOPES}/{id}", json={"pool_end": "10.10.0.250"}).json()

    assert (updated["pool_end"], updated["dns_servers"], updated["gateway"]) == (
        "10.10.0.250",
        ["10.0.0.53"],
        "10.10.0.1",
    )


def test_dns_can_be_cleared(api):
    id = api.post(SCOPES, json={**SCOPE, "dns_servers": ["10.0.0.53"], "domain_name": "ztp.lab"}).json()["id"]

    updated = api.patch(f"{SCOPES}/{id}", json={"dns_servers": None, "domain_name": None}).json()

    assert (updated["dns_servers"], updated["domain_name"]) == ([], None)


def test_a_scope_can_be_deleted(api):
    id = api.post(SCOPES, json=SCOPE).json()["id"]

    assert api.delete(f"{SCOPES}/{id}").status_code == 204
    assert api.get(SCOPES).json() == []


def test_an_unknown_id_is_not_found(api):
    assert api.patch(f"{SCOPES}/99", json={"description": "x"}).status_code == 404
    assert api.delete(f"{SCOPES}/99").status_code == 404
