import asyncio
import base64
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from acex.api.routers.node_instances import create_router
from acex.device_configs import device_config_manager as module
from acex.device_configs.device_config_manager import DeviceConfigManager
from acex.models import DeviceConfig, StoredDeviceConfig
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

START = datetime(2026, 10, 22, 8, 0, tzinfo=UTC)
LATER = START + timedelta(hours=6)
LATEST = START + timedelta(hours=12)


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


@pytest.fixture
def clock(monkeypatch):
    now = SimpleNamespace(value=START)
    monkeypatch.setattr(module, "datetime", SimpleNamespace(now=lambda tz=None: now.value))
    return now


@pytest.fixture
def manager(clock):
    async def get_node(node_instance_id):
        return SimpleNamespace(asset=SimpleNamespace(ned_id=None))

    async def no_ned(node_instance):
        return None

    manager = DeviceConfigManager(_Db(), inventory=SimpleNamespace(node_instances=SimpleNamespace(get=get_node)))
    manager._get_ned = no_ned
    return manager


def encoded(text):
    return base64.b64encode(text.encode()).decode()


def upload(manager, text, node="1"):
    return asyncio.run(manager.upload_config(DeviceConfig(node_instance_id=node, content=encoded(text))))


def stored_rows(manager, node="1"):
    with Session(manager.db.engine) as session:
        statement = select(StoredDeviceConfig).where(StoredDeviceConfig.node_instance_id == node)
        return session.exec(statement.order_by(StoredDeviceConfig.id)).all()


def as_utc(moment):
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def times(row):
    """created_at and last_collected_at as UTC, whether or not the database kept the zone."""
    return as_utc(row.created_at), as_utc(row.last_collected_at)


def test_a_first_upload_is_collected_when_it_is_stored(manager):
    upload(manager, "hostname core-1")

    (stored,) = stored_rows(manager)
    assert times(stored) == (START, START)


def test_an_unchanged_upload_is_refused_but_moves_the_collection_time(manager, clock):
    upload(manager, "hostname core-1")
    clock.value = LATER

    with pytest.raises(HTTPException) as refused:
        upload(manager, "hostname core-1")

    assert refused.value.status_code == 409
    (stored,) = stored_rows(manager)
    assert times(stored) == (START, LATER)


def test_a_changed_upload_is_a_new_snapshot_and_the_old_one_keeps_its_last_collection(manager, clock):
    upload(manager, "hostname core-1")
    clock.value = LATER
    with pytest.raises(HTTPException):
        upload(manager, "hostname core-1")
    clock.value = LATEST

    upload(manager, "hostname core-2")

    old, new = stored_rows(manager)
    assert times(old) == (START, LATER)
    assert times(new) == (LATEST, LATEST)


def test_each_node_keeps_its_own_collection_time(manager, clock):
    upload(manager, "hostname core-1", node="1")
    upload(manager, "hostname core-1", node="2")
    clock.value = LATER

    with pytest.raises(HTTPException):
        upload(manager, "hostname core-1", node="2")

    assert times(stored_rows(manager, node="1")[0]) == (START, START)
    assert times(stored_rows(manager, node="2")[0]) == (START, LATER)


def test_the_latest_config_reports_when_it_was_last_collected(manager, clock):
    upload(manager, "hostname core-1")
    clock.value = LATER
    with pytest.raises(HTTPException):
        upload(manager, "hostname core-1")

    latest = asyncio.run(manager.get_latest_config("1"))

    assert times(latest) == (START, LATER)


def test_the_history_shows_when_each_snapshot_was_last_collected(manager, clock):
    upload(manager, "hostname core-1")
    clock.value = LATER
    with pytest.raises(HTTPException):
        upload(manager, "hostname core-1")
    clock.value = LATEST
    upload(manager, "hostname core-2")

    newest, oldest = manager.list_config_hashes("1")

    assert (as_utc(newest["created_at"]), as_utc(newest["last_collected_at"])) == (LATEST, LATEST)
    assert (as_utc(oldest["created_at"]), as_utc(oldest["last_collected_at"])) == (START, LATER)


def test_the_observed_endpoints_return_last_collected_at(manager, clock):
    async def get_rendered_config(id: str):
        return ""

    node_instances = SimpleNamespace(capabilities=[], get_rendered_config=get_rendered_config)
    engine = SimpleNamespace(inventory=SimpleNamespace(node_instances=node_instances), device_config_manager=manager)
    app = FastAPI()
    app.include_router(create_router(engine))
    client = TestClient(app)
    url = "/api/v1/inventory/node_instances/1/configuration/observed"

    assert client.post(url, json={"content": encoded("hostname core-1")}).status_code == 200
    clock.value = LATER
    assert client.post(url, json={"content": encoded("hostname core-1")}).status_code == 409

    latest = client.get(f"{url}/latest").json()
    by_id = client.get(f"{url}/{latest['id']}").json()
    history = client.get(f"{url}?limit=1").json()

    assert latest["created_at"].startswith("2026-10-22T08:00:00")
    assert latest["last_collected_at"].startswith("2026-10-22T14:00:00")
    assert by_id["last_collected_at"] == latest["last_collected_at"]
    assert datetime.fromisoformat(history[0]["last_collected_at"]) == LATER
