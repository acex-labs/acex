"""ZTP vendor classes: free-text DHCP vendor classes, each mapped to one ZTP method or none."""

from types import SimpleNamespace

import pytest
from acex.api import auth
from acex.api.routers.ztp_vendor_classes import create_router
from acex.models.ztp_vendor_class import ZtpVendorClassRow
from acex.ztp import ZtpVendorClassManager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

VENDOR_CLASSES = "/api/v1/ztp_vendor_classes"


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
    engine = SimpleNamespace(ztp_vendor_classes=ZtpVendorClassManager(db))
    app = FastAPI()
    app.include_router(create_router(engine))
    app.dependency_overrides[auth.get_current_user] = lambda: {"preferred_username": "alice"}
    return TestClient(app)


def test_a_vendor_class_is_unmapped_until_a_method_is_chosen(api):
    response = api.post(VENDOR_CLASSES, json={"vendor_class": "ciscopnp"})

    assert response.status_code == 201
    created = response.json()
    assert (created["vendor_class"], created["method"], created["updated_by"]) == ("ciscopnp", None, "alice")


def test_vendor_classes_are_listed_by_name(api):
    api.post(VENDOR_CLASSES, json={"vendor_class": "Juniper-mx"})
    api.post(VENDOR_CLASSES, json={"vendor_class": "ciscopnp", "method": "cisco_iosxe_python"})

    listed = api.get(VENDOR_CLASSES).json()

    assert [(v["vendor_class"], v["method"]) for v in listed] == [
        ("Juniper-mx", None),
        ("ciscopnp", "cisco_iosxe_python"),
    ]


def test_surrounding_whitespace_is_dropped(api):
    assert api.post(VENDOR_CLASSES, json={"vendor_class": "  ciscopnp "}).json()["vendor_class"] == "ciscopnp"


def test_an_empty_vendor_class_is_refused(api):
    assert api.post(VENDOR_CLASSES, json={"vendor_class": "  "}).status_code == 422


def test_a_vendor_class_can_only_exist_once(api):
    api.post(VENDOR_CLASSES, json={"vendor_class": "ciscopnp"})

    assert api.post(VENDOR_CLASSES, json={"vendor_class": "ciscopnp"}).status_code == 409


def test_an_unknown_method_is_refused(api):
    assert api.post(VENDOR_CLASSES, json={"vendor_class": "ciscopnp", "method": "junos_ztp"}).status_code == 422


def test_a_vendor_class_is_mapped_and_unmapped(api):
    id = api.post(VENDOR_CLASSES, json={"vendor_class": "ciscopnp"}).json()["id"]

    mapped = api.patch(f"{VENDOR_CLASSES}/{id}", json={"method": "cisco_iosxe_python"})
    assert (mapped.status_code, mapped.json()["method"]) == (200, "cisco_iosxe_python")

    unmapped = api.patch(f"{VENDOR_CLASSES}/{id}", json={"method": None})
    assert (unmapped.status_code, unmapped.json()["method"]) == (200, None)


def test_renaming_keeps_the_method(api):
    id = api.post(VENDOR_CLASSES, json={"vendor_class": "ciscopnp", "method": "cisco_iosxe_python"}).json()["id"]

    renamed = api.patch(f"{VENDOR_CLASSES}/{id}", json={"vendor_class": "ciscopnp-ng"}).json()

    assert (renamed["vendor_class"], renamed["method"]) == ("ciscopnp-ng", "cisco_iosxe_python")


def test_renaming_to_an_existing_vendor_class_is_refused(api):
    api.post(VENDOR_CLASSES, json={"vendor_class": "ciscopnp"})
    id = api.post(VENDOR_CLASSES, json={"vendor_class": "Juniper-mx"}).json()["id"]

    assert api.patch(f"{VENDOR_CLASSES}/{id}", json={"vendor_class": "ciscopnp"}).status_code == 409


def test_a_vendor_class_can_be_deleted(api):
    id = api.post(VENDOR_CLASSES, json={"vendor_class": "ciscopnp"}).json()["id"]

    assert api.delete(f"{VENDOR_CLASSES}/{id}").status_code == 204
    assert api.get(VENDOR_CLASSES).json() == []


def test_an_unknown_id_is_not_found(api):
    assert api.patch(f"{VENDOR_CLASSES}/99", json={"method": None}).status_code == 404
    assert api.delete(f"{VENDOR_CLASSES}/99").status_code == 404


def test_a_vendor_class_is_matched_exactly_unless_told_otherwise(api):
    exact = api.post(VENDOR_CLASSES, json={"vendor_class": "ciscopnp"}).json()
    prefix = api.post(VENDOR_CLASSES, json={"vendor_class": "Juniper-", "match": "prefix"}).json()

    assert (exact["match"], prefix["match"]) == ("exact", "prefix")


def _mapped_elsewhere(db, vendor_class, match="exact"):
    """A row mapped to another method than cisco_iosxe_python, the only one there is so far."""
    with Session(db.engine) as session:
        session.add(ZtpVendorClassRow(vendor_class=vendor_class, match=match, method="other_method"))
        session.commit()


def test_a_prefix_covering_a_vendor_class_of_another_method_is_refused(api, db):
    _mapped_elsewhere(db, "Juniper-mx")

    response = api.post(
        VENDOR_CLASSES, json={"vendor_class": "Juniper", "match": "prefix", "method": "cisco_iosxe_python"}
    )

    assert response.status_code == 409
    assert "Juniper-mx" in response.json()["detail"]


def test_a_vendor_class_under_a_prefix_of_another_method_is_refused(api, db):
    _mapped_elsewhere(db, "Juniper", match="prefix")

    response = api.post(VENDOR_CLASSES, json={"vendor_class": "Juniper-mx", "method": "cisco_iosxe_python"})

    assert response.status_code == 409


def test_overlaps_with_the_same_method_or_unmapped_are_fine(api, db):
    _mapped_elsewhere(db, "Juniper-mx")

    unmapped = api.post(VENDOR_CLASSES, json={"vendor_class": "Juniper", "match": "prefix"})
    same = api.post(VENDOR_CLASSES, json={"vendor_class": "Arista", "match": "prefix", "method": "cisco_iosxe_python"})
    under_same = api.post(VENDOR_CLASSES, json={"vendor_class": "Arista-7050", "method": "cisco_iosxe_python"})

    assert (unmapped.status_code, same.status_code, under_same.status_code) == (201, 201, 201)


def test_mapping_an_overlapping_vendor_class_to_another_method_is_refused(api, db):
    _mapped_elsewhere(db, "Juniper", match="prefix")
    id = api.post(VENDOR_CLASSES, json={"vendor_class": "Juniper-mx"}).json()["id"]

    assert api.patch(f"{VENDOR_CLASSES}/{id}", json={"method": "cisco_iosxe_python"}).status_code == 409


def test_a_vendor_class_with_a_quote_is_refused(api):
    assert api.post(VENDOR_CLASSES, json={"vendor_class": "it's"}).status_code == 422
