"""Tests for building the worker's Celery app from a WorkerConnection."""

from __future__ import annotations

from acex_devkit.models.worker import WorkerConnection
from acex_worker.app import create_app

CONNECTION = WorkerConnection.model_validate(
    {
        "broker": {"host": "rabbitmq", "port": 5672, "vhost": "/", "user": "acex", "password": "p@ss/word"},
        "queues": [{"name": "acex.ztp", "durable": True}],
    }
)


def test_app_connects_to_the_broker_it_was_handed():
    app = create_app(CONNECTION, ["acex.ztp.discover"])

    connection = app.connection_for_read()
    assert (connection.hostname, connection.port) == ("rabbitmq", 5672)
    assert (connection.userid, connection.password) == ("acex", "p@ss/word")
    assert connection.virtual_host == "/"


def test_app_declares_the_queues_as_handed_out():
    app = create_app(CONNECTION, ["acex.ztp.discover"])

    assert [(queue.name, queue.durable) for queue in app.conf.task_queues] == [("acex.ztp", True)]


def test_app_has_a_task_per_job_type():
    app = create_app(CONNECTION, ["acex.ztp.discover", "acex.ztp.provision"])

    assert {"acex.ztp.discover", "acex.ztp.provision"} <= set(app.tasks)
