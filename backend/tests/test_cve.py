from types import SimpleNamespace

import pytest
from acex.api import auth as _auth
from acex.api.routers.cves import create_router
from acex.credentials.credential_manager import CredentialManager
from acex.cve.cve_manager import CveManager
from acex.models.credential import Credential, CredentialField, NodeCredential, SiteCredential
from acex.models.cve import CveModelRow, CveState, SyncState
from acex_devkit.models.credential import CredentialCreate
from acex_devkit.models.cve import CveCreate
from acex_devkit.models.job import JobResponse
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select


class _Db:
    def __init__(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(
            self.engine,
            tables=[
                CveModelRow.__table__,
                CveState.__table__,
                SyncState.__table__,
                Credential.__table__,
                CredentialField.__table__,
                NodeCredential.__table__,
                SiteCredential.__table__,
            ],
        )

    def get_session(self):
        with Session(self.engine) as session:
            yield session


def _payload(cve_id: str, *, description: str = "First description") -> CveCreate:
    return CveCreate(
        cve_id=cve_id,
        description=description,
        raw={"id": cve_id, "description": description},
    )


def test_bulk_create_inserts_and_refreshes_without_duplicate_rows():
    db = _Db()
    manager = CveManager(db)

    first = manager.bulk_create([CveCreate(cve_id="CVE-2026-0001", base_severity="HIGH", raw={"id": "CVE-2026-0001"})])
    first_created_at = first[0].created_at
    refreshed = manager.bulk_create(
        [
            CveCreate(
                cve_id="CVE-2026-0001",
                description="Updated description",
                base_severity="CRITICAL",
                raw={"id": "CVE-2026-0001"},
            )
        ]
    )

    assert len(refreshed) == 1
    assert refreshed[0].id == first[0].id
    assert refreshed[0].created_at == first_created_at
    assert refreshed[0].updated_at is not None
    assert refreshed[0].description == "Updated description"
    assert refreshed[0].base_severity == "CRITICAL"
    with Session(db.engine) as session:
        assert len(session.exec(select(CveModelRow)).all()) == 1


def test_bulk_create_deduplicates_repeated_ids_in_one_payload():
    manager = CveManager(_Db())

    created = manager.bulk_create([_payload("CVE-2026-0001"), _payload("CVE-2026-0001", description="Last")])

    assert len(created) == 1
    assert created[0].description == "Last"


def test_bulk_create_api_accepts_a_list_of_payload_dicts():
    manager = CveManager(_Db())
    app = FastAPI()
    app.include_router(create_router(SimpleNamespace(cves=manager)))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/cves/bulk",
            json=[
                {
                    "cve_id": "CVE-2026-0001",
                    "description": "Example",
                    "raw": {"id": "CVE-2026-0001"},
                },
                {
                    "cve_id": "CVE-2026-0002",
                    "description": "Another",
                    "raw": {"id": "CVE-2026-0002"},
                },
            ],
        )

    assert response.status_code == 200
    assert {item["cve_id"] for item in response.json()} == {
        "CVE-2026-0001",
        "CVE-2026-0002",
    }


def test_discover_api_creates_a_worker_job():
    class _Jobs:
        def enqueue(self, job_type, payload, *, created_by):
            assert job_type == "acex.cve.discover"
            assert payload.vendor == "Cisco"
            assert created_by == "alice"
            return JobResponse.model_validate(
                {
                    "id": 18,
                    "type": job_type,
                    "data": payload.model_dump(mode="json"),
                    "state": "queued",
                    "created_by": created_by,
                    "created_at": "2026-01-01T00:00:00Z",
                }
            )

    app = FastAPI()
    app.include_router(create_router(SimpleNamespace(cves=None, jobs=_Jobs())))
    app.dependency_overrides[_auth.get_current_user] = lambda: {"sub": "alice"}

    with TestClient(app) as client:
        response = client.post("/api/v1/cves/discover", json={})

    assert response.status_code == 202
    assert response.json()["type"] == "acex.cve.discover"


@pytest.fixture
def key_api():
    db = _Db()
    encryption_key = Fernet.generate_key().decode()
    cm = CredentialManager(db, encryption_key)
    engine = SimpleNamespace(cves=CveManager(db), credential_manager=cm)
    app = FastAPI()
    app.include_router(create_router(engine))
    app.dependency_overrides[_auth.get_current_user] = lambda: {"sub": "worker"}
    with TestClient(app) as client:
        yield client, engine, db, encryption_key


def test_nvd_key_round_trip_is_encrypted_persistent_and_not_echoed(key_api):
    client, engine, db, encryption_key = key_api
    response = client.get("/api/v1/cves/api_key")
    assert response.status_code == 200
    assert response.json() is None
    assert response.headers["cache-control"] == "no-store"

    saved = client.put("/api/v1/cves/api_key", json={"api_key": "test-nvd-key"})
    assert saved.status_code == 204
    assert saved.content == b""
    with Session(db.engine) as session:
        fields = session.exec(select(CredentialField)).all()
        assert len(fields) == 1
        assert fields[0].field_value != "test-nvd-key"
        assert Fernet(encryption_key.encode()).decrypt(fields[0].field_value.encode()) == b"test-nvd-key"

    # Rebuild the manager to prove the key is not just cached in memory.
    engine.credential_manager = CredentialManager(db, encryption_key)
    response = client.get("/api/v1/cves/api_key")
    assert response.status_code == 200
    assert response.json() == "test-nvd-key"
    assert response.headers["cache-control"] == "no-store"
    assert engine.credential_manager.query()[0].fields[0].field_value is None

    assert client.put("/api/v1/cves/api_key", json={"api_key": "replacement"}).status_code == 204
    assert client.get("/api/v1/cves/api_key").json() == "replacement"
    assert len(engine.credential_manager.query()) == 1

    for _ in range(2):
        deleted = client.delete("/api/v1/cves/api_key")
        assert deleted.status_code == 204
        assert deleted.content == b""
    assert client.get("/api/v1/cves/api_key").json() is None
    with Session(db.engine) as session:
        assert session.exec(select(CredentialField)).all() == []


@pytest.mark.parametrize("payload", [{}, {"api_key": ""}, {"api_key": " \n "}, {"api_key": None}])
def test_nvd_key_rejects_empty_values_without_changing_the_key(key_api, payload):
    client, *_ = key_api
    client.put("/api/v1/cves/api_key", json={"api_key": "kept"})
    assert client.put("/api/v1/cves/api_key", json=payload).status_code == 422
    assert client.get("/api/v1/cves/api_key").json() == "kept"


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_nvd_key_requires_authentication_even_on_a_standalone_router(monkeypatch, method):
    monkeypatch.setattr(_auth, "OIDC_ISSUER_URL", "https://idp.example")
    app = FastAPI()
    app.include_router(create_router(SimpleNamespace(cves=None)))
    with TestClient(app) as client:
        response = client.request(method, "/api/v1/cves/api_key", json={"api_key": "unused"})
    assert response.status_code == 401


def test_nvd_key_ignores_other_credentials_with_the_same_prefix(key_api):
    client, engine, *_ = key_api
    engine.credential_manager.create(
        CredentialCreate(
            name="acex.cve.nvd.other",
            credential_type="token",
            fields={"token": "unrelated"},
        )
    )
    assert client.get("/api/v1/cves/api_key").json() is None
    assert client.delete("/api/v1/cves/api_key").status_code == 204
    assert len(engine.credential_manager.query()) == 1


def test_nvd_key_rejects_a_conflicting_credential(key_api):
    client, engine, *_ = key_api
    engine.credential_manager.create(
        CredentialCreate(
            name="acex.cve.nvd",
            credential_type="userpass",
            fields={"password": "unrelated"},
        )
    )
    for method in ("GET", "PUT", "DELETE"):
        response = client.request(method, "/api/v1/cves/api_key", json={"api_key": "new"})
        assert response.status_code == 409
    assert len(engine.credential_manager.query()) == 1


def _list_api(manager):
    app = FastAPI()
    app.include_router(create_router(SimpleNamespace(cves=manager)))
    return TestClient(app)


def test_list_cves_returns_stable_non_overlapping_pages_with_total():
    manager = CveManager(_Db())
    manager.bulk_create([_payload(f"CVE-2026-{n:04d}") for n in range(5)])

    with _list_api(manager) as client:
        first = client.get("/api/v1/cves", params={"limit": 2, "offset": 0}).json()
        second = client.get("/api/v1/cves", params={"limit": 2, "offset": 2}).json()
        last = client.get("/api/v1/cves", params={"limit": 2, "offset": 4}).json()

    assert (first["total"], first["limit"], first["offset"]) == (5, 2, 0)
    assert (second["limit"], second["offset"]) == (2, 2)
    ids = [item["cve_id"] for page in (first, second, last) for item in page["items"]]
    assert ids == [f"CVE-2026-{n:04d}" for n in range(5)]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 1001}, {"offset": -1}])
def test_list_cves_rejects_out_of_range_pagination(params):
    with _list_api(CveManager(_Db())) as client:
        assert client.get("/api/v1/cves", params=params).status_code == 422
