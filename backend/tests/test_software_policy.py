"""Software policy: the versions approved per vendor or hardware model, at most one of them golden."""

from types import SimpleNamespace

import pytest
from acex.api import auth
from acex.api.routers.policies import create_router
from acex.models import Asset
from acex.policies import SoftwarePolicyManager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

SOFTWARE = "/api/v1/policies/software"
C9300 = {"vendor": "cisco", "hardware_model": "C9300-24T", "os": "cisco_iosxe", "os_version": "17.9.4a"}


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
    engine = SimpleNamespace(software_policies=SoftwarePolicyManager(db))
    app = FastAPI()
    app.include_router(create_router(engine))
    app.dependency_overrides[auth.get_current_user] = lambda: {"preferred_username": "alice"}
    return TestClient(app)


def test_a_version_is_approved_as_accepted_unless_golden(api):
    response = api.post(SOFTWARE, json=C9300)

    assert response.status_code == 201
    created = response.json()
    assert (created["os_version"], created["golden"], created["updated_by"]) == ("17.9.4a", False, "alice")
    assert api.get(f"{SOFTWARE}/{created['id']}").json() == created


def test_versions_are_listed_vendor_first_and_golden_first(api):
    api.post(SOFTWARE, json={**C9300, "os_version": "17.6.5"})
    api.post(SOFTWARE, json={**C9300, "golden": True})
    api.post(SOFTWARE, json={**C9300, "hardware_model": None, "os_version": "17.3.1"})

    listed = [(p["hardware_model"], p["os_version"]) for p in api.get(SOFTWARE).json()]

    assert listed == [(None, "17.3.1"), ("C9300-24T", "17.9.4a"), ("C9300-24T", "17.6.5")]


def test_a_model_is_stored_as_the_devkit_declares_it(api):
    assert api.post(SOFTWARE, json={**C9300, "hardware_model": "c9300-24t"}).json()["hardware_model"] == "C9300-24T"


def test_a_blank_hardware_model_is_the_vendors(api):
    assert api.post(SOFTWARE, json={**C9300, "hardware_model": "  "}).json()["hardware_model"] is None


def test_a_version_is_approved_once(api):
    api.post(SOFTWARE, json=C9300)
    assert api.post(SOFTWARE, json=C9300).status_code == 409


def test_the_same_version_may_be_approved_for_the_vendor_and_a_model(api):
    api.post(SOFTWARE, json=C9300)
    assert api.post(SOFTWARE, json={**C9300, "hardware_model": None}).status_code == 201


def test_a_second_golden_version_is_refused(api):
    api.post(SOFTWARE, json={**C9300, "golden": True})

    response = api.post(SOFTWARE, json={**C9300, "os_version": "17.12.1", "golden": True})

    assert response.status_code == 409
    assert "17.9.4a" in response.json()["detail"]


def test_a_vendor_and_each_model_have_a_golden_version_of_their_own(api):
    api.post(SOFTWARE, json={**C9300, "golden": True})
    assert api.post(SOFTWARE, json={**C9300, "hardware_model": None, "golden": True}).status_code == 201


def test_each_os_of_a_vendor_has_a_golden_version_of_its_own(api):
    nxos = {"vendor": "cisco", "os": "cisco_nxos", "os_version": "10.2.5", "golden": True}
    api.post(SOFTWARE, json={**C9300, "hardware_model": None, "golden": True})

    assert api.post(SOFTWARE, json=nxos).status_code == 201

    second = api.post(SOFTWARE, json={**nxos, "os_version": "10.3.1"})
    assert second.status_code == 409
    assert "cisco_nxos" in second.json()["detail"] and "10.2.5" in second.json()["detail"]
    assert api.post(SOFTWARE, json={**nxos, "os_version": "10.3.1", "golden": False}).status_code == 201


def test_versions_are_listed_os_by_os(api):
    vendor = {"vendor": "cisco", "hardware_model": None}
    api.post(SOFTWARE, json={**vendor, "os": "cisco_nxos", "os_version": "10.2.5", "golden": True})
    api.post(SOFTWARE, json={**vendor, "os": "cisco_iosxe", "os_version": "17.6.5"})
    api.post(SOFTWARE, json={**vendor, "os": "cisco_iosxe", "os_version": "17.9.4a", "golden": True})

    listed = [(p["os"], p["os_version"]) for p in api.get(SOFTWARE).json()]

    assert listed == [("cisco_iosxe", "17.9.4a"), ("cisco_iosxe", "17.6.5"), ("cisco_nxos", "10.2.5")]


@pytest.mark.parametrize(
    "changes",
    [
        {"os": "cisco_nxos", "os_version": "10.2.5"},  # not an OS the model runs
        {"vendor": "juniper", "os": "juniper_junos", "os_version": "22.4R1"},  # not the model's vendor
        {"os_version": "seventeen"},  # not a version the OS can report
    ],
)
def test_a_version_that_does_not_hold_together_is_refused(api, changes):
    assert api.post(SOFTWARE, json={**C9300, **changes}).status_code == 422


def test_golden_is_handed_over_by_making_the_old_one_accepted(api):
    old = api.post(SOFTWARE, json={**C9300, "golden": True}).json()
    new = api.post(SOFTWARE, json={**C9300, "os_version": "17.12.1"}).json()

    assert api.patch(f"{SOFTWARE}/{new['id']}", json={"golden": True}).status_code == 409
    assert api.patch(f"{SOFTWARE}/{old['id']}", json={"golden": False}).json()["golden"] is False
    assert api.patch(f"{SOFTWARE}/{new['id']}", json={"golden": True}).json()["golden"] is True


def test_an_update_is_checked_as_a_whole(api):
    created = api.post(SOFTWARE, json=C9300).json()

    response = api.patch(f"{SOFTWARE}/{created['id']}", json={"os": "cisco_nxos"})

    assert response.status_code == 422
    assert api.get(f"{SOFTWARE}/{created['id']}").json()["os"] == "cisco_iosxe"


def test_a_version_can_be_withdrawn(api):
    created = api.post(SOFTWARE, json=C9300).json()

    assert api.delete(f"{SOFTWARE}/{created['id']}").status_code == 204
    assert api.get(f"{SOFTWARE}/{created['id']}").status_code == 404
    assert api.delete(f"{SOFTWARE}/{created['id']}").status_code == 404


def test_a_version_the_os_can_not_report_is_refused_with_examples(api):
    response = api.post(SOFTWARE, json={**C9300, "os_version": "17.8"})

    assert response.status_code == 422
    assert "e.g. 17.9.4a" in response.json()["detail"][0]["msg"]


def add_assets(db, *assets):
    with Session(db.engine) as session:
        for i, (hardware_model, os_version) in enumerate(assets):
            session.add(
                Asset(
                    vendor="cisco",
                    serial_number=f"SN{i}",
                    os="cisco_iosxe",
                    hardware_model=hardware_model,
                    os_version=os_version,
                )
            )
        session.commit()


def test_the_versions_assets_run_are_suggested_newest_first(api, db):
    add_assets(
        db,
        ("C9300-24T", "17.9.4a"),
        ("c9300-24t", "17.9.4a"),
        ("C9300-24T", "17.12.3a"),
        ("C9300-24T", "16.12.5b"),
        ("C9300-48P", "17.6.5"),
        ("C9300-24T", None),
    )
    params = {"vendor": "cisco", "os": "cisco_iosxe"}

    for_model = api.get(f"{SOFTWARE}/versions", params={**params, "hardware_model": "C9300-24T"}).json()
    for_vendor = api.get(f"{SOFTWARE}/versions", params=params).json()

    assert [(v["os_version"], v["assets"]) for v in for_model] == [("17.12.3a", 1), ("17.9.4a", 2), ("16.12.5b", 1)]
    assert [v["os_version"] for v in for_vendor] == ["17.12.3a", "17.9.4a", "17.6.5", "16.12.5b"]
    assert api.get(f"{SOFTWARE}/versions", params={"vendor": "juniper", "os": "juniper_junos"}).json() == []
