"""The workers API: listing jobs, and the reports a worker makes on one — a
claim, then success or failure. A report that does not fit the job's state is
refused with 409, so a redelivered or stray message is never run twice."""

from types import SimpleNamespace

import pytest
from acex.api import auth
from acex.api.routers.workers import create_router
from acex.jobs import JobManager, JobType, JobTypeRegistry
from acex.settings import RabbitMQSettings
from acex_devkit.models.job import JobSubjectType
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

JOBS = "/api/v1/workers/jobs"


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


class _Producer:
    configured = True

    def publish(self, job_type: str, job_id: int) -> None:
        pass


class _NodeData(BaseModel):
    node_id: int


class _PingResult(BaseModel):
    reachable: bool
    rtt_ms: float | None = None


def _registry() -> JobTypeRegistry:
    job_types = JobTypeRegistry()
    job_types.register(JobType("acex.ztp.discover", data=_NodeData, subject=(JobSubjectType.node, "node_id")))
    job_types.register(
        JobType("acex.ztp.ping", data=_NodeData, result=_PingResult, subject=(JobSubjectType.node, "node_id"))
    )
    return job_types


class _Api:
    """The router on a fresh database, with the caller's identity switchable."""

    def __init__(self, rabbitmq: RabbitMQSettings | None = None):
        self.jobs = JobManager(_Db(), _Producer(), _registry())
        self.caller = {"azp": "worker-a"}
        settings = SimpleNamespace(rabbitmq=rabbitmq or RabbitMQSettings())
        app = FastAPI()
        app.include_router(create_router(SimpleNamespace(jobs=self.jobs, settings=settings)))
        app.dependency_overrides[auth.get_current_user] = lambda: self.caller
        self.client = TestClient(app)

    def job(self, job_type: str = "acex.ztp.discover", node_id: int = 1) -> int:
        return self.jobs.enqueue(job_type, {"node_id": node_id}, created_by="alice").id

    def as_worker(self, name: str) -> "_Api":
        self.caller = {"azp": name}
        return self

    def patch(self, job_id: int, **report):
        return self.client.patch(f"{JOBS}/{job_id}", json=report)


@pytest.fixture
def api():
    return _Api()


class TestListing:
    def should_list_top_level_jobs_newest_first(self, api):
        first, second = api.job(node_id=1), api.job(node_id=2)
        api.jobs.enqueue_batch("acex.ztp.discover", [{"node_id": 3}], created_by="alice")

        page = api.client.get(JOBS).json()

        assert page["total"] == 3
        assert [job["id"] for job in page["items"]][1:] == [second, first]

    def should_summarise_without_data(self, api):
        api.job()
        [job] = api.client.get(JOBS).json()["items"]
        assert "data" not in job
        assert job["state"] == "queued"

    def should_list_a_batch_through_its_parent(self, api):
        parent = api.jobs.enqueue_batch("acex.ztp.discover", [{"node_id": n} for n in (1, 2)], created_by="alice")

        [listed] = api.client.get(JOBS).json()["items"]
        children = api.client.get(JOBS, params={"parent_id": parent.id}).json()

        assert listed["children"]["queued"] == 2
        assert children["total"] == 2

    def should_filter(self, api):
        api.job(node_id=1)
        ping = api.job("acex.ztp.ping", node_id=2)
        api.patch(ping, state="running")

        assert [j["id"] for j in api.client.get(JOBS, params={"type": "acex.ztp.ping"}).json()["items"]] == [ping]
        assert [j["id"] for j in api.client.get(JOBS, params={"state": "running"}).json()["items"]] == [ping]
        by_subject = api.client.get(JOBS, params={"subject_type": "node", "subject_id": 2}).json()["items"]
        assert [j["id"] for j in by_subject] == [ping]

    def should_leave_batch_parents_out_of_a_state_filter(self, api):
        api.jobs.enqueue_batch("acex.ztp.discover", [{"node_id": 1}], created_by="alice")
        assert api.client.get(JOBS, params={"state": "queued"}).json()["total"] == 0

    def should_paginate(self, api):
        for node in range(5):
            api.job(node_id=node)
        page = api.client.get(JOBS, params={"limit": 2, "offset": 2}).json()
        assert (page["total"], page["limit"], page["offset"], len(page["items"])) == (5, 2, 2, 2)


class TestOneJob:
    def should_show_everything(self, api):
        job = api.client.get(f"{JOBS}/{api.job(node_id=7)}").json()
        assert job["data"] == {"node_id": 7}

    def should_answer_404_for_an_unknown_job(self, api):
        assert api.client.get(f"{JOBS}/999").status_code == 404
        assert api.patch(999, state="running").status_code == 404


class TestClaim:
    def should_hand_the_job_to_the_worker(self, api):
        response = api.patch(api.job(node_id=7), state="running")

        assert response.status_code == 200
        job = response.json()
        assert (job["state"], job["claimed_by"], job["attempts"]) == ("running", "worker-a", 1)
        assert job["started_at"] is not None
        assert job["data"] == {"node_id": 7}  # no second request needed to start work

    def should_refuse_a_job_another_worker_has(self, api):
        job_id = api.job()
        api.patch(job_id, state="running")

        response = api.as_worker("worker-b").patch(job_id, state="running")

        assert response.status_code == 409
        assert response.json()["detail"]["job"]["claimed_by"] == "worker-a"

    def should_accept_a_repeated_claim_from_the_same_worker(self, api):
        job_id = api.job()
        api.patch(job_id, state="running")

        response = api.patch(job_id, state="running")

        assert response.status_code == 200
        assert response.json()["attempts"] == 1

    def should_refuse_a_finished_job(self, api):
        job_id = api.job()
        api.patch(job_id, state="running")
        api.patch(job_id, state="succeeded")

        assert api.as_worker("worker-b").patch(job_id, state="running").status_code == 409

    def should_refuse_a_batch_parent(self, api):
        parent = api.jobs.enqueue_batch("acex.ztp.discover", [{"node_id": 1}], created_by="alice")
        assert api.patch(parent.id, state="running").status_code == 409


class TestFinish:
    def should_store_a_valid_result(self, api):
        job_id = api.job("acex.ztp.ping")
        api.patch(job_id, state="running")

        job = api.patch(job_id, state="succeeded", result={"reachable": True, "rtt_ms": 1.5}).json()

        assert (job["state"], job["result"]) == ("succeeded", {"reachable": True, "rtt_ms": 1.5})
        assert job["finished_at"] is not None

    def should_refuse_a_result_that_does_not_fit(self, api):
        job_id = api.job("acex.ztp.ping")
        api.patch(job_id, state="running")

        assert api.patch(job_id, state="succeeded", result={"rtt_ms": "fast"}).status_code == 422
        assert api.patch(job_id, state="succeeded").status_code == 422  # this type needs a result
        assert api.client.get(f"{JOBS}/{job_id}").json()["state"] == "running"

    def should_refuse_a_result_from_a_type_that_gives_none(self, api):
        job_id = api.job()
        api.patch(job_id, state="running")
        assert api.patch(job_id, state="succeeded", result={"anything": 1}).status_code == 422

    def should_record_a_failure(self, api):
        job_id = api.job()
        api.patch(job_id, state="running")

        job = api.patch(job_id, state="failed", error="SSH never came up").json()

        assert (job["state"], job["error"]) == ("failed", "SSH never came up")

    def should_need_an_error_to_fail(self, api):
        job_id = api.job()
        api.patch(job_id, state="running")
        assert api.patch(job_id, state="failed").status_code == 422

    def should_accept_a_repeated_report(self, api):
        job_id = api.job()
        api.patch(job_id, state="running")
        api.patch(job_id, state="succeeded")

        assert api.patch(job_id, state="succeeded").status_code == 200

    def should_refuse_a_report_on_a_job_the_worker_does_not_hold(self, api):
        job_id = api.job()
        assert api.patch(job_id, state="succeeded").status_code == 409  # never claimed

        api.patch(job_id, state="running")
        assert api.as_worker("worker-b").patch(job_id, state="failed", error="x").status_code == 409


class TestConnect:
    BROKER = RabbitMQSettings(host="rabbitmq", port=5672, vhost="acex", user="acex", password="s3cr/et")

    def should_hand_out_the_broker_and_the_queues_for_its_job_types(self):
        api = _Api(rabbitmq=self.BROKER)

        response = api.client.post(
            "/api/v1/workers/connect", json={"job_types": ["acex.ztp.discover", "acex.ztp.ping"]}
        )

        assert response.status_code == 200
        assert response.json() == {
            "broker": {"host": "rabbitmq", "port": 5672, "vhost": "acex", "user": "acex", "password": "s3cr/et"},
            "queues": [{"name": "acex.ztp", "durable": True}],
        }

    def should_refuse_a_job_type_the_backend_does_not_create(self):
        # Routed to acex.ztp, but no such job type is registered: a worker with
        # a handler for it would never be sent a job.
        response = _Api(rabbitmq=self.BROKER).client.post(
            "/api/v1/workers/connect", json={"job_types": ["acex.ztp.provision"]}
        )
        assert response.status_code == 422
        assert "acex.ztp.discover" in response.json()["detail"]  # names the ones that exist

    def should_refuse_no_job_types(self):
        response = _Api(rabbitmq=self.BROKER).client.post("/api/v1/workers/connect", json={"job_types": []})
        assert response.status_code == 422

    def should_answer_503_without_a_broker(self):
        response = _Api().client.post("/api/v1/workers/connect", json={"job_types": ["acex.ztp.discover"]})
        assert response.status_code == 503


class TestJobTypes:
    def should_list_every_job_type_and_its_queue(self, api):
        assert api.client.get("/api/v1/workers/job_types").json() == [
            {"name": "acex.ztp.discover", "queue": "acex.ztp"},
            {"name": "acex.ztp.ping", "queue": "acex.ztp"},
        ]

    def should_need_no_broker(self, api):
        # Nothing about the broker is handed out, so it answers either way.
        assert api.client.get("/api/v1/workers/job_types").status_code == 200
