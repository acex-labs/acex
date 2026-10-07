from acex.messaging.settings import RabbitMQSettings
from celery import Celery

DEFAULT_QUEUE = "acex.default"
PROVISION_QUEUE = "acex.provision"


def make_celery_app(settings: RabbitMQSettings | None = None) -> Celery:
    settings = settings or RabbitMQSettings.from_env()
    app = Celery(
        "acex",
        broker=settings.url,
        backend=settings.result_backend,
        include=["acex.messaging.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_default_queue=DEFAULT_QUEUE,
        task_routes={"acex.provision.*": {"queue": PROVISION_QUEUE}},
        # A task is acknowledged after it finishes, so a worker that dies
        # mid-task hands it back to the queue instead of losing it.
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        result_expires=3600,
        broker_connection_retry_on_startup=True,
        # RabbitMQ 4.1+ refuses transient non-exclusive queues, which is what
        # Celery's remote-control and event (gossip) queues are by default.
        control_queue_exclusive=True,
        event_queue_exclusive=True,
    )
    return app


celery_app = make_celery_app()
