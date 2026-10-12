"""A device that fetches its ZTP bootstrap gets a discovery job, and gets its
bootstrap whether or not that job could be queued — as long as the method has
a bootstrap login for discovery to use."""

from types import SimpleNamespace

import pytest
from acex.api.routers.ztp import create_router
from acex.jobs import JobManager
from acex.models.job import Job, JobState
from acex.ztp import ZtpMethodManager
from acex_devkit.models.ztp import ZtpMethod, ZtpMethodUpdate
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

BOOTSTRAP = "/api/v1/ztp/init_config/cisco_iosxe_python/ztp.py"
DEVICE_IP = "10.1.2.3"


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


class _Producer:
    def __init__(self, configured: bool = True, fails: bool = False):
        self.configured = configured
        self.fails = fails
        self.published: list[tuple[str, int]] = []

    def publish(self, job_type: str, job_id: int) -> None:
        if self.fails:
            raise ConnectionError("broker unreachable")
        self.published.append((job_type, job_id))


@pytest.fixture
def db():
    return _Db()


def _fetch_bootstrap(db, producer, login=("acex-ztp", "Temp123")):
    methods = ZtpMethodManager(db, neds=set)
    if login:
        username, password = login
        methods.update(
            ZtpMethod.cisco_iosxe_python,
            ZtpMethodUpdate(bootstrap_username=username, bootstrap_password=password),
            updated_by="alice",
        )
    app = FastAPI()
    app.include_router(create_router(SimpleNamespace(jobs=JobManager(db, producer), ztp_methods=methods)))
    return TestClient(app, client=(DEVICE_IP, 50000)).get(BOOTSTRAP)


def _jobs(db) -> list[Job]:
    with Session(db.engine) as session:
        return list(session.exec(select(Job)).all())


class TestBootstrapFetch:
    def should_queue_discovery_of_the_device(self, db):
        producer = _Producer()
        response = _fetch_bootstrap(db, producer)

        assert response.status_code == 200
        [job] = _jobs(db)
        assert job.type == "acex.ztp.discover"
        assert job.data == {"ip": DEVICE_IP, "method": "cisco_iosxe_python"}
        assert job.created_by == "system"
        assert producer.published == [("acex.ztp.discover", job.id)]

    def should_serve_the_bootstrap_without_a_broker(self, db):
        response = _fetch_bootstrap(db, _Producer(configured=False))

        assert response.status_code == 200
        assert response.text.startswith("#!/usr/bin/env python")
        assert _jobs(db) == []

    def should_serve_the_bootstrap_when_the_job_cannot_be_published(self, db):
        response = _fetch_bootstrap(db, _Producer(fails=True))

        assert response.status_code == 200
        [job] = _jobs(db)
        assert job.state == JobState.failed


class TestBootstrapLogin:
    def should_give_the_device_the_methods_login(self, db):
        response = _fetch_bootstrap(db, _Producer())

        assert "'username acex-ztp privilege 15 secret 0 Temp123'," in response.text

    def should_keep_a_login_from_breaking_out_of_the_script(self, db):
        response = _fetch_bootstrap(db, _Producer(), login=("acex", "x',\nimport os #"))

        compile(response.text, "ztp.py", "exec")
        assert "\nimport os" not in response.text

    def should_refuse_the_bootstrap_without_a_login(self, db):
        response = _fetch_bootstrap(db, _Producer(), login=None)

        assert response.status_code == 503
        assert _jobs(db) == []
