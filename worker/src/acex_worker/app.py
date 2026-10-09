"""The worker's Celery app, built from what the acex API hands out at startup."""

from __future__ import annotations

import logging
from urllib.parse import quote

from acex_devkit.models.worker import BrokerConnection, WorkerConnection
from celery import Celery
from kombu import Queue

log = logging.getLogger("acex_worker")


def broker_url(broker: BrokerConnection) -> str:
    credentials = ""
    if broker.user is not None:
        credentials = quote(broker.user, safe="")
        if broker.password is not None:
            credentials += ":" + quote(broker.password.get_secret_value(), safe="")
        credentials += "@"
    return f"amqp://{credentials}{broker.host}:{broker.port}/{quote(broker.vhost, safe='')}"


def create_app(connection: WorkerConnection, job_types: list[str]) -> Celery:
    """A Celery app that consumes the given queues and has a task for each job type.

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
    for job_type in job_types:
        _register(app, job_type)
    return app


def _register(app: Celery, job_type: str) -> None:
    @app.task(name=job_type)
    def run_job(job_id: int) -> None:
        log.info(f"Received job {job_id} ({job_type})")

        log.info("Nu ska vi logga in i switchen!")
        log.info("Logga in i swirren och hämta s/n, os och os_ver")
        log.info("Kolla i acex om serienummer finns på asset")
        log.info("Skapa asset om S/n inte finns")
        log.info("Mappa mot befintlig asset om s/n finns sedan innan")
