"""Tests for building the worker's Celery app and running jobs through their handlers."""

from __future__ import annotations

import json

import pytest
import respx
from acex_client import Acex
from acex_devkit.models.job import JobResponse
from acex_devkit.models.worker import WorkerConnection
from acex_worker.app import create_app, execute
from acex_worker.handlers.base_handler import Handler
from httpx import Response
from pydantic import BaseModel

BASE = "http://test"
API = f"{BASE}/api/v1"

CONNECTION = WorkerConnection.model_validate(
    {
        "broker": {"host": "rabbitmq", "port": 5672, "vhost": "/", "user": "acex", "password": "p@ss/word"},
        "queues": [{"name": "acex.ztp", "durable": True}],
    }
)


class EchoData(BaseModel):
    text: str


class EchoResult(BaseModel):
    echoed: str


class Echo(Handler):
    def handle(self, client: Acex, job: JobResponse) -> dict:
        data = EchoData.model_validate(job.data)
        if data.text == "boom":
            raise RuntimeError("it went boom")
        return EchoResult(echoed=data.text).model_dump()


class Nothing(Handler):
    def handle(self, client: Acex, job: JobResponse) -> dict:
        return None


HANDLERS = {"acex.test.echo": Echo, "acex.test.other": Echo}


def job(job_id: int, state: str, data: dict | None = None) -> dict:
    return {
        "id": job_id,
        "type": "acex.test.echo",
        "data": data,
        "state": state,
        "created_by": "system",
        "created_at": "2026-10-09T00:00:00Z",
    }


@pytest.fixture
def client():
    with respx.mock:
        respx.get(f"{API}/auth/config").mock(return_value=Response(200, json={"enabled": False}))
        with Acex(BASE) as client:
            yield client


def test_app_connects_to_the_broker_it_was_handed(client):
    app = create_app(CONNECTION, client, HANDLERS)

    connection = app.connection_for_read()
    assert (connection.hostname, connection.port) == ("rabbitmq", 5672)
    assert (connection.userid, connection.password) == ("acex", "p@ss/word")
    assert connection.virtual_host == "/"


def test_app_declares_the_queues_as_handed_out(client):
    app = create_app(CONNECTION, client, HANDLERS)

    assert [(queue.name, queue.durable) for queue in app.conf.task_queues] == [("acex.ztp", True)]


def test_app_has_a_task_per_job_type(client):
    app = create_app(CONNECTION, client, HANDLERS)

    assert {"acex.test.echo", "acex.test.other"} <= set(app.tasks)


def reports(route) -> list[dict]:
    return [json.loads(call.request.content) for call in route.calls]


def test_a_job_is_claimed_run_and_reported_with_its_result(client):
    route = respx.patch(f"{API}/workers/jobs/7").mock(
        side_effect=[
            Response(200, json=job(7, "running", {"text": "hi"})),
            Response(200, json=job(7, "succeeded", {"text": "hi"})),
        ]
    )

    execute(client, "acex.test.echo", Echo, 7)

    assert reports(route) == [
        {"state": "running"},
        {"state": "succeeded", "result": {"echoed": "hi"}},
    ]


def test_a_handler_that_raises_fails_the_job(client):
    route = respx.patch(f"{API}/workers/jobs/7").mock(
        side_effect=[
            Response(200, json=job(7, "running", {"text": "boom"})),
            Response(200, json=job(7, "failed", {"text": "boom"})),
        ]
    )

    execute(client, "acex.test.echo", Echo, 7)

    assert reports(route)[1] == {"state": "failed", "error": "it went boom"}


def test_data_that_does_not_fit_the_job_type_fails_the_job(client):
    route = respx.patch(f"{API}/workers/jobs/7").mock(
        side_effect=[
            Response(200, json=job(7, "running", {"wrong": "field"})),
            Response(200, json=job(7, "failed")),
        ]
    )

    execute(client, "acex.test.echo", Echo, 7)

    assert reports(route)[1]["state"] == "failed"


def test_a_handler_that_returns_nothing_fails_the_job(client):
    route = respx.patch(f"{API}/workers/jobs/7").mock(
        side_effect=[
            Response(200, json=job(7, "running", {"text": "hi"})),
            Response(200, json=job(7, "failed", {"text": "hi"})),
        ]
    )

    execute(client, "acex.test.echo", Nothing, 7)

    assert reports(route)[1] == {"state": "failed", "error": "Handler returned None"}


def test_a_result_the_backend_rejects_fails_the_job(client):
    route = respx.patch(f"{API}/workers/jobs/7").mock(
        side_effect=[
            Response(200, json=job(7, "running", {"text": "hi"})),
            Response(422, json={"detail": "result does not fit"}),
            Response(200, json=job(7, "failed", {"text": "hi"})),
        ]
    )

    execute(client, "acex.test.echo", Echo, 7)

    last = reports(route)[2]
    assert last["state"] == "failed"
    assert last["error"].startswith("result rejected:")


def test_a_job_that_cannot_be_claimed_is_skipped(client):
    route = respx.patch(f"{API}/workers/jobs/7").mock(return_value=Response(409, json={"detail": "job 7 is succeeded"}))

    execute(client, "acex.test.echo", Echo, 7)

    assert len(route.calls) == 1
