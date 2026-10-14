"""Tests for the workers resource via respx mocks."""

from __future__ import annotations

import json

import pytest
import respx
from acex_client.auth import NullAuthProvider
from acex_client.exceptions import AcexConflictError
from acex_client.http import RestClient
from acex_client.resources.workers import Workers
from acex_devkit.models.worker import WorkerConnectRequest
from httpx import Response
from pydantic import BaseModel

API = "http://test/api/v1"

JOB = {
    "id": 6,
    "type": "acex.ztp.discover",
    "data": {"ip": "10.1.2.3", "method": "cisco_iosxe_python"},
    "state": "running",
    "attempts": 1,
    "created_by": "system",
    "claimed_by": "worker-a",
    "created_at": "2026-10-08T10:43:14",
}


@pytest.fixture
def workers():
    rest = RestClient(API, NullAuthProvider(), timeout=5.0)
    try:
        yield Workers(rest)
    finally:
        rest.close()


@respx.mock
def test_connect_hands_out_broker_and_queues(workers):
    route = respx.post(f"{API}/workers/connect").mock(
        return_value=Response(
            200,
            json={
                "broker": {"host": "rabbitmq", "port": 5672, "vhost": "/", "user": "acex", "password": "pw"},
                "queues": [{"name": "acex.ztp", "durable": True}],
            },
        )
    )

    connection = workers.connect(payload=WorkerConnectRequest(job_types=["acex.ztp.discover"]))

    assert json.loads(route.calls[0].request.content) == {"job_types": ["acex.ztp.discover"]}
    assert connection.broker.password.get_secret_value() == "pw"
    assert "pw" not in repr(connection)
    assert [queue.name for queue in connection.queues] == ["acex.ztp"]


@respx.mock
def test_claim_takes_the_job(workers):
    route = respx.patch(f"{API}/workers/jobs/6").mock(return_value=Response(200, json=JOB))

    job = workers.jobs.claim(6)

    assert json.loads(route.calls[0].request.content) == {"state": "running"}
    assert job.data == {"ip": "10.1.2.3", "method": "cisco_iosxe_python"}


@respx.mock
def test_claim_conflict_raises(workers):
    respx.patch(f"{API}/workers/jobs/6").mock(return_value=Response(409, json={"detail": {"reason": "taken"}}))
    with pytest.raises(AcexConflictError):
        workers.jobs.claim(6)


@respx.mock
def test_succeed_sends_the_result(workers):
    class Result(BaseModel):
        serial_number: str

    route = respx.patch(f"{API}/workers/jobs/6").mock(return_value=Response(200, json={**JOB, "state": "succeeded"}))

    workers.jobs.succeed(6, Result(serial_number="FOC123"))

    assert json.loads(route.calls[0].request.content) == {"state": "succeeded", "result": {"serial_number": "FOC123"}}


@respx.mock
def test_fail_sends_the_error(workers):
    route = respx.patch(f"{API}/workers/jobs/6").mock(return_value=Response(200, json={**JOB, "state": "failed"}))

    workers.jobs.fail(6, "SSH never came up")

    assert json.loads(route.calls[0].request.content) == {"state": "failed", "error": "SSH never came up"}


@respx.mock
def test_query_lists_summaries(workers):
    respx.get(f"{API}/workers/jobs").mock(
        return_value=Response(
            200,
            json={
                "items": [{k: JOB[k] for k in ("id", "type", "state", "attempts", "created_at")}],
                "total": 1,
                "limit": 100,
                "offset": 0,
            },
        )
    )

    page = workers.jobs.query(state="running")

    assert [job.id for job in page] == [6]


@respx.mock
def test_job_types_lists_job_types_and_queues(workers):
    respx.get(f"{API}/workers/job_types").mock(
        return_value=Response(200, json=[{"name": "acex.ztp.discover", "queue": "acex.ztp"}])
    )

    [job_type] = workers.job_types()

    assert (job_type.name, job_type.queue) == ("acex.ztp.discover", "acex.ztp")
