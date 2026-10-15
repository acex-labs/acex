from pydantic import BaseModel, Field, SecretStr, field_serializer


class JobTypeInfo(BaseModel):
    """A job type the backend creates, and the queue that carries it."""

    name: str
    queue: str


class WorkerConnectRequest(BaseModel):
    """What a starting worker can run, so it is told which queues carry those jobs."""

    job_types: list[str] = Field(min_length=1)


class BrokerConnection(BaseModel):
    """The RabbitMQ broker a worker consumes from."""

    host: str
    port: int
    vhost: str
    user: str | None = None
    #: Hidden in repr and logs, but sent in full: the worker has to log in with it.
    password: SecretStr | None = None

    @field_serializer("password", when_used="json")
    def _send_password(self, password: SecretStr | None) -> str | None:
        return password.get_secret_value() if password is not None else None


class QueueDeclaration(BaseModel):
    """A queue as the backend declares it. A worker must declare it the same
    way: RabbitMQ refuses a second declaration with different arguments."""

    name: str
    durable: bool


class WorkerConnection(BaseModel):
    """Everything a worker needs to start consuming, handed out by the API."""

    broker: BrokerConnection
    queues: list[QueueDeclaration]
