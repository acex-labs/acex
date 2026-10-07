import os
from urllib.parse import quote

from pydantic import BaseModel

ENV_PREFIX = "ACEX_RABBITMQ_"


class RabbitMQSettings(BaseModel):
    """Broker connection for background tasks, from ACEX_RABBITMQ_* env vars.

    ACEX_RABBITMQ_URL wins; otherwise HOST, PORT, USER, PASSWORD and VHOST are
    combined. With neither set, messaging is disabled.
    """

    url: str | None = None
    # Celery's "rpc://" backend cannot be used: RabbitMQ 4.1+ refuses the
    # transient non-exclusive reply queue it declares. Unset means results
    # are not stored and callers cannot wait for them.
    result_backend: str | None = None

    @classmethod
    def from_env(cls) -> "RabbitMQSettings":
        url = os.environ.get(f"{ENV_PREFIX}URL")
        host = os.environ.get(f"{ENV_PREFIX}HOST")
        if not url and host:
            user = quote(os.environ.get(f"{ENV_PREFIX}USER", "guest"), safe="")
            password = quote(os.environ.get(f"{ENV_PREFIX}PASSWORD", "guest"), safe="")
            port = os.environ.get(f"{ENV_PREFIX}PORT", "5672")
            vhost = quote(os.environ.get(f"{ENV_PREFIX}VHOST", "/"), safe="")
            url = f"amqp://{user}:{password}@{host}:{port}/{vhost}"
        return cls(
            url=url or None,
            result_backend=os.environ.get(f"{ENV_PREFIX}RESULT_BACKEND") or None,
        )

    @property
    def enabled(self) -> bool:
        return self.url is not None
