"""The worker's Celery app, built from what the acex API hands out at startup."""

from __future__ import annotations

import logging
from urllib.parse import quote

from acex_client import Acex
from acex_client.exceptions import AcexConflictError, AcexError
from acex_devkit.models.worker import BrokerConnection, WorkerConnection
from celery import Celery
from kombu import Queue

from .handlers.base_handler import Handler

log = logging.getLogger("acex_worker")


def broker_url(broker: BrokerConnection) -> str:
    credentials = ""
    if broker.user is not None:
        credentials = quote(broker.user, safe="")
        if broker.password is not None:
            credentials += ":" + quote(broker.password.get_secret_value(), safe="")
        credentials += "@"
    return f"amqp://{credentials}{broker.host}:{broker.port}/{quote(broker.vhost, safe='')}"


def create_app(connection: WorkerConnection, client: Acex, handlers: dict[str, type[Handler]]) -> Celery:
    """A Celery app that consumes the given queues and has a task for each handler.

    Building it does not connect; the worker connects when it starts.
    """
    app = Celery("acex_worker", broker=broker_url(connection.broker))
    app.conf.update(
        # Declared exactly as the backend declares them: RabbitMQ refuses a
        # second declaration with different arguments.
        task_queues=[Queue(queue.name, durable=queue.durable) for queue in connection.queues],
        accept_content=["json"],
        # A message is acknowledged once its job has run, so a worker that dies
        # mid-job leaves it to be redelivered; the claim makes that safe.
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        # Celery's remote control talks over transient queues, which RabbitMQ 4
        # refuses. Nothing uses it: the jobs table is where jobs are watched.
        worker_enable_remote_control=False,
        # Threads, not processes: the tasks are registered at runtime, so a
        # spawned child process would not have them. Jobs mostly wait on I/O.
        worker_pool="threads",
    )
    for job_type, handler in handlers.items():
        _register(app, client, job_type, handler)
    return app


def _register(app: Celery, client: Acex, job_type: str, handler: type[Handler]) -> None:
    # Celery routes a message to the task named after its job type.
    @app.task(name=job_type)
    def run_job(job_id: int) -> None:
        execute(client, job_type, handler, job_id)


def execute(client: Acex, job_type: str, handler: type[Handler], job_id: int) -> None:
    """Claim the job, run its handler, and report how it ended."""
    log.info(f"Received job {job_id} ({job_type})")
    try:
        job = client.workers.jobs.claim(job_id)
    except AcexConflictError:
        # A redelivery of a job that already ended, or one that was cancelled.
        log.info(f"Job {job_id} is finished or cancelled, skipping it")
        return
    response = handler().handle_hook(client, job)
    if not response.success:
        log.error(f"Job {job_id} ({job_type}) failed: {response.error}")
        client.workers.jobs.fail(job_id, response.error)
        return
    try:
        client.workers.jobs.succeed(job_id, response.result)
    except AcexError as exc:
        # The backend validates the result against the job type's model.
        log.exception(f"Job {job_id} ({job_type}) result rejected")
        client.workers.jobs.fail(job_id, f"result rejected: {exc}")
        return
    log.info(f"Job {job_id} ({job_type}) succeeded")
