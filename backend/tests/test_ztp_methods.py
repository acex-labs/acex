"""ZTP methods: one row per method in code, holding the NED an administrator chose for it."""

from types import SimpleNamespace

import pytest
from acex.api import auth
from acex.api.routers.ztp_methods import create_router
from acex.models.ztp_method import ZtpMethodRow
from acex.ztp import ZtpMethodManager
from acex_devkit.models.ztp import ZTP_METHOD_INFO, ZtpMethod
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

METHODS = "/api/v1/ztp_methods"


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


@pytest.fixture
def db():
    return _Db()


@pytest.fixture
def api(db):
    engine = SimpleNamespace(ztp_methods=ZtpMethodManager(db, neds=lambda: {"CiscoIOSCLIDriver"}))
    app = FastAPI()
    app.include_router(create_router(engine))
    app.dependency_overrides[auth.get_current_user] = lambda: {"preferred_username": "alice"}
    return TestClient(app)


def test_every_method_is_listed_without_a_ned_until_one_is_chosen(api):
    response = api.get(METHODS)

    assert response.status_code == 200
    assert [(m["method"], m["ned"], m["updated_at"]) for m in response.json()] == [("cisco_iosxe_python", None, None)]


def test_every_method_has_a_label_and_description():
    assert set(ZTP_METHOD_INFO) == set(ZtpMethod)


def test_a_method_comes_with_its_label_and_description(api):
    method = api.get(f"{METHODS}/cisco_iosxe_python").json()

    assert method["label"] == "Cisco IOS XE — Python"
    assert "guestshell" in method["description"]


def test_a_method_missing_from_the_database_gets_its_row(api, db):
    api.get(f"{METHODS}/cisco_iosxe_python")

    with Session(db.engine) as session:
        assert session.get(ZtpMethodRow, "cisco_iosxe_python") is not None


def test_choosing_a_ned_is_kept_with_who_chose_it(api):
    response = api.put(f"{METHODS}/cisco_iosxe_python", json={"ned": "CiscoIOSCLIDriver"})

    assert response.status_code == 200
    method = api.get(f"{METHODS}/cisco_iosxe_python").json()
    assert method["ned"] == "CiscoIOSCLIDriver"
    assert method["updated_by"] == "alice"
    assert method["updated_at"] is not None


def test_a_ned_that_is_not_installed_is_refused(api):
    response = api.put(f"{METHODS}/cisco_iosxe_python", json={"ned": "NoSuchDriver"})

    assert response.status_code == 422
    assert api.get(f"{METHODS}/cisco_iosxe_python").json()["ned"] is None


def test_the_ned_can_be_cleared(api):
    api.put(f"{METHODS}/cisco_iosxe_python", json={"ned": "CiscoIOSCLIDriver"})

    response = api.put(f"{METHODS}/cisco_iosxe_python", json={"ned": None})

    assert response.status_code == 200
    assert response.json()["ned"] is None


def test_an_unknown_method_is_refused(api):
    assert api.get(f"{METHODS}/junos_ztp").status_code == 422


def test_the_bootstrap_login_is_kept_and_shown(api):
    response = api.put(
        f"{METHODS}/cisco_iosxe_python", json={"bootstrap_username": "acex-ztp", "bootstrap_password": "Temp123"}
    )

    assert response.status_code == 200
    method = api.get(f"{METHODS}/cisco_iosxe_python").json()
    assert (method["bootstrap_username"], method["bootstrap_password"]) == ("acex-ztp", "Temp123")


def test_fields_left_out_of_an_update_keep_their_value(api):
    api.put(f"{METHODS}/cisco_iosxe_python", json={"ned": "CiscoIOSCLIDriver"})

    api.put(f"{METHODS}/cisco_iosxe_python", json={"bootstrap_username": "acex-ztp"})

    method = api.get(f"{METHODS}/cisco_iosxe_python").json()
    assert method["ned"] == "CiscoIOSCLIDriver"
    assert method["bootstrap_username"] == "acex-ztp"
