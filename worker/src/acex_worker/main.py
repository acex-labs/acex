"""Starting a worker: log in to the acex API and ask it where to consume from."""

from __future__ import annotations

import logging
import os
import sys

import httpx
from acex_client import Acex, AcexError
from acex_client.auth import AuthorizationCodeAuth, AuthProvider, create_auth_provider
from acex_devkit.models.worker import WorkerConnection, WorkerConnectRequest

from acex_worker.app import create_app
from acex_worker.registry import HANDLERS

log = logging.getLogger("acex_worker")

#: The job types this worker has code for, so it only ever asks for jobs it can run.
JOB_TYPES = list(HANDLERS)


class StartupError(Exception):
    """The worker cannot start, for a reason it can explain."""


def _auth(api_url: str) -> AuthProvider:
    """The worker's service account. Never a browser login: nobody is there to finish it."""
    auth = create_auth_provider(api_url)
    if isinstance(auth, AuthorizationCodeAuth):
        raise StartupError("The backend requires login: set ACEX_CLIENT_ID and ACEX_CLIENT_SECRET.")
    return auth


def connect_client() -> Acex:
    """An acex client logged in as the worker, configured from ACEX_* env vars."""
    base_url = os.environ.get("ACEX_BASE_URL", "http://127.0.0.1:8080/")
    return Acex.from_env(base_url, auth=_auth(f"{base_url.rstrip('/')}/api/v1"))


def start(client: Acex) -> WorkerConnection:
    """Fetch the broker and queues that carry this worker's job types."""
    return client.workers.connect(payload=WorkerConnectRequest(job_types=JOB_TYPES))


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log.info(f"Starting worker for job types: {', '.join(JOB_TYPES)}")
    try:
        client = connect_client()
        connection = start(client)
    except (StartupError, AcexError, httpx.HTTPError) as exc:
        log.error(f"Worker could not start: {exc}")
        sys.exit(1)

    broker = connection.broker
    log.info(f"Broker: {broker.user}@{broker.host}:{broker.port} vhost {broker.vhost}")
    for queue in connection.queues:
        log.info(f"Queue: {queue.name} (durable={queue.durable})")

    app = create_app(connection, client, HANDLERS)
    # Runs until stopped. -Q keeps Celery off its default "celery" queue.
    # Mingle and gossip are worker-to-worker chatter over the same transient
    # queues as remote control.
    queues = ",".join(queue.name for queue in connection.queues)
    with client:
        app.worker_main(["worker", "--loglevel=INFO", "-Q", queues, "--without-mingle", "--without-gossip"])


if __name__ == "__main__":
    run()
