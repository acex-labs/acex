"""ZTP call-ins: every bootstrap fetch is a discovery job, shown one device per
IP with how far discovery got."""

from types import SimpleNamespace

import acex.models  # noqa: F401  (every table, for create_all)
import pytest
from acex.api import auth
from acex.api.routers.workers import create_router as workers_router
from acex.api.routers.ztp_calls import create_router as calls_router
from acex.jobs import JobManager
from acex.settings import RabbitMQSettings
from acex.ztp import ZtpCallManager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

CALLS = "/api/v1/ztp_calls"
JOBS = "/api/v1/workers/jobs"


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


class _Producer:
    def __init__(self):
        self.configured = True

    def publish(self, job_type: str, job_id: int) -> None:
        pass


class _Ztp:
    def __init__(self):
        self.db = _Db()
        self.producer = _Producer()
        self.jobs = JobManager(self.db, self.producer)
        engine = SimpleNamespace(
            jobs=self.jobs,
            settings=SimpleNamespace(rabbitmq=RabbitMQSettings()),
            ztp_calls=ZtpCallManager(self.db, self.jobs),
        )
        app = FastAPI()
        app.include_router(workers_router(engine))
        app.include_router(calls_router(engine))
        app.dependency_overrides[auth.get_current_user] = lambda: {"azp": "worker-a", "sub": "alice"}
        self.client = TestClient(app)

    def call_in(self, ip: str) -> int:
        """A device at `ip` fetches its bootstrap."""
        return self.jobs.enqueue(
            "acex.ztp.discover", {"ip": ip, "method": "cisco_iosxe_python"}, created_by="system"
        ).id

    def claim(self, job_id: int) -> None:
        self.client.patch(f"{JOBS}/{job_id}", json={"state": "running"})

    def fail(self, job_id: int, error: str = "SSH refused") -> None:
        self.claim(job_id)
        self.client.patch(f"{JOBS}/{job_id}", json={"state": "failed", "error": error})

    def report(self, job_id: int, serial: str) -> None:
        self.claim(job_id)
        self.client.patch(f"{JOBS}/{job_id}", json={"state": "succeeded", "result": {"serial_number": serial}})

    def calls(self, **params) -> list[dict]:
        return self.client.get(CALLS, params=params).json()["items"]


@pytest.fixture
def ztp():
    return _Ztp()


class TestStages:
    def should_follow_the_latest_discovery_job(self, ztp):
        ztp.call_in("10.0.0.1")
        ztp.claim(ztp.call_in("10.0.0.2"))
        ztp.fail(ztp.call_in("10.0.0.3"))
        ztp.report(ztp.call_in("10.0.0.4"), "FOC1")

        stages = {c["source_ip"]: c["stage"] for c in ztp.calls()}

        assert stages == {
            "10.0.0.1": "waiting",
            "10.0.0.2": "discovering",
            "10.0.0.3": "failed",
            "10.0.0.4": "reported",
        }

    def should_show_the_reported_serial_and_the_error(self, ztp):
        ztp.fail(ztp.call_in("10.0.0.3"), "SSH refused")
        ztp.report(ztp.call_in("10.0.0.4"), "FOC1")

        by_ip = {c["source_ip"]: c["attempts"][0] for c in ztp.calls()}

        assert by_ip["10.0.0.3"]["error"] == "SSH refused"
        assert (by_ip["10.0.0.4"]["serial_number"], by_ip["10.0.0.4"]["review_status"]) == ("FOC1", "unreviewed")

    def should_filter_on_stage(self, ztp):
        ztp.call_in("10.0.0.1")
        ztp.fail(ztp.call_in("10.0.0.3"))
        assert [c["source_ip"] for c in ztp.calls(stage="failed")] == ["10.0.0.3"]


class TestGrouping:
    def should_gather_a_device_calling_in_again_under_its_ip(self, ztp):
        first = ztp.call_in("10.0.0.1")
        ztp.fail(first)
        second = ztp.call_in("10.0.0.1")

        [call] = ztp.calls()

        assert [a["job_id"] for a in call["attempts"]] == [second, first]
        assert call["stage"] == "waiting"  # the latest attempt decides

    def should_list_the_most_recently_seen_first(self, ztp):
        ztp.call_in("10.0.0.1")
        ztp.call_in("10.0.0.2")
        ztp.call_in("10.0.0.1")
        assert [c["source_ip"] for c in ztp.calls()] == ["10.0.0.1", "10.0.0.2"]


class TestRetry:
    def should_queue_discovery_again(self, ztp):
        ztp.fail(ztp.call_in("10.0.0.3"))

        call = ztp.client.post(f"{CALLS}/10.0.0.3/retry").json()

        assert call["stage"] == "waiting"
        assert len(call["attempts"]) == 2

    def should_answer_404_for_an_ip_that_never_called_in(self, ztp):
        assert ztp.client.post(f"{CALLS}/10.9.9.9/retry").status_code == 404

    def should_answer_503_without_a_broker(self, ztp):
        ztp.fail(ztp.call_in("10.0.0.3"))
        ztp.producer.configured = False
        assert ztp.client.post(f"{CALLS}/10.0.0.3/retry").status_code == 503


def should_keep_call_ins_out_of_the_public_ztp_prefix():
    assert not any(CALLS == p or CALLS.startswith(f"{p}/") for p in auth._PUBLIC_PATH_PREFIXES)
