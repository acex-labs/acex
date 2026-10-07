from acex.messaging.routing import QUEUES, queue_for
from acex.settings import RabbitMQSettings
from celery import Celery
from kombu import Queue


class MessagingNotConfigured(RuntimeError):
    pass


class JobProducer:
    """Puts job ids on their queues for workers to consume.

    The backend only publishes; workers only consume and have their own Celery
    setup. What both must agree on is how the queues are declared: durable
    classic queues with no arguments. Building the Celery app does not connect;
    the connection is opened by the first publish.
    """

    def __init__(self, settings: RabbitMQSettings):
        self._app = self._make_app(settings) if settings.configured else None

    @property
    def configured(self) -> bool:
        return self._app is not None

    def publish(self, job_type: str, job_id: int) -> None:
        if self._app is None:
            raise MessagingNotConfigured("RabbitMQ is not configured; set ACEX_RABBITMQ_HOST to run jobs.")
        # The job id doubles as Celery's task id, so one id finds a job in
        # acex, in Celery's logs and in RabbitMQ.
        self._app.send_task(job_type, args=[job_id], task_id=str(job_id), queue=queue_for(job_type))

    @staticmethod
    def _make_app(settings: RabbitMQSettings) -> Celery:
        app = Celery("acex", broker=settings.url)
        app.conf.update(
            task_serializer="json",
            # Declared on publish, so a job sent before any worker has started
            # waits in its queue instead of being dropped. The jobs table, not
            # the broker, is the record of what has to run.
            task_queues=[Queue(name, durable=True) for name in QUEUES],
            task_create_missing_queues=False,
            # Fail a publish quickly instead of holding up the request that made it.
            broker_transport_options={"confirm_publish": True},
            task_publish_retry_policy={"max_retries": 2, "interval_start": 0, "interval_step": 0.5, "interval_max": 1},
        )
        return app
