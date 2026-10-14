"""The Kea config for ZTP: a client class per mapped method, the default method for the rest, a subnet per scope."""

from types import SimpleNamespace

import pytest
from acex.api import auth
from acex.api.routers.ztp_dhcp import create_router
from acex.ztp import KeaConfigRenderer, ZtpDhcpScopeManager, ZtpMethodManager, ZtpVendorClassManager
from acex.ztp.bootstrap import BOOTSTRAPS
from acex_devkit.models.ztp import (
    ZtpDhcpScopeCreate,
    ZtpMethod,
    ZtpMethodUpdate,
    ZtpVendorClassCreate,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

BOOTSTRAP_URL = "http://acex.lab:8080/api/v1/ztp/init_config/cisco_iosxe_python/ztp.py"
CISCO_OPTIONS = [{"name": "boot-file-name", "data": BOOTSTRAP_URL}]


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


@pytest.fixture
def ztp():
    db = _Db()
    methods = ZtpMethodManager(db, neds=set)
    vendor_classes = ZtpVendorClassManager(db)
    scopes = ZtpDhcpScopeManager(db)
    return SimpleNamespace(
        methods=methods,
        vendor_classes=vendor_classes,
        scopes=scopes,
        kea=KeaConfigRenderer(methods, vendor_classes, scopes),
    )


def _render(ztp) -> dict:
    return ztp.kea.render("http://acex.lab:8080/")["Dhcp4"]


def _map(ztp, vendor_class, match="exact", method=ZtpMethod.cisco_iosxe_python):
    ztp.vendor_classes.create(
        ZtpVendorClassCreate(vendor_class=vendor_class, match=match, method=method), updated_by="alice"
    )


def test_every_method_has_a_bootstrap():
    assert set(BOOTSTRAPS) == set(ZtpMethod)


def test_nothing_mapped_gives_no_client_classes(ztp):
    _map(ztp, "ciscopnp", method=None)

    assert _render(ztp)["client-classes"] == []


def test_a_mapped_method_gets_a_class_matching_its_vendor_classes(ztp):
    _map(ztp, "ciscopnp")
    _map(ztp, "Arista", match="prefix")

    [cls] = _render(ztp)["client-classes"]

    assert cls == {
        "name": "ztp-cisco_iosxe_python",
        "test": "substring(option[60].text,0,6) == 'Arista' or option[60].text == 'ciscopnp'",
        "option-data": CISCO_OPTIONS,
    }


def test_the_default_method_takes_the_devices_no_class_matched(ztp):
    _map(ztp, "ciscopnp")
    ztp.methods.update(ZtpMethod.cisco_iosxe_python, ZtpMethodUpdate(is_default=True), updated_by="alice")

    classes = _render(ztp)["client-classes"]

    assert classes[-1] == {
        "name": "ztp-default",
        "test": "not member('ztp-cisco_iosxe_python')",
        "option-data": CISCO_OPTIONS,
    }


def test_a_default_method_alone_matches_every_device(ztp):
    ztp.methods.update(ZtpMethod.cisco_iosxe_python, ZtpMethodUpdate(is_default=True), updated_by="alice")

    [cls] = _render(ztp)["client-classes"]

    assert cls["test"] == "member('ALL')"


def test_a_scope_becomes_a_subnet_with_addressing_only(ztp):
    ztp.scopes.create(
        ZtpDhcpScopeCreate(
            network="10.10.0.0/24",
            pool_start="10.10.0.100",
            pool_end="10.10.0.199",
            gateway="10.10.0.1",
            dns_servers=["10.0.0.53", "10.0.1.53"],
            domain_name="ztp.lab",
        ),
        updated_by="alice",
    )

    [subnet] = _render(ztp)["subnet4"]

    assert subnet == {
        "id": 1,
        "subnet": "10.10.0.0/24",
        "pools": [{"pool": "10.10.0.100 - 10.10.0.199"}],
        "option-data": [
            {"name": "routers", "data": "10.10.0.1"},
            {"name": "domain-name-servers", "data": "10.0.0.53, 10.0.1.53"},
            {"name": "domain-name", "data": "ztp.lab"},
        ],
    }


def test_the_api_points_bootstraps_to_the_address_it_was_reached_on(ztp):
    _map(ztp, "ciscopnp")
    app = FastAPI()
    app.include_router(create_router(SimpleNamespace(ztp_kea=ztp.kea)))
    app.dependency_overrides[auth.get_current_user] = lambda: {}

    response = TestClient(app, base_url="http://acex.lab:8080").get("/api/v1/ztp_dhcp/kea")

    assert response.status_code == 200
    assert response.json()["Dhcp4"]["client-classes"][0]["option-data"] == CISCO_OPTIONS
