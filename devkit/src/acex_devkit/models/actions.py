"""Actions a driver can run from a device. Each action has its own params and result model."""

from typing import ClassVar

from pydantic import BaseModel


class ActionParams(BaseModel):
    """Base for action parameters. `action` names the `Actions` method that runs it."""

    action: ClassVar[str]


class PingParams(ActionParams):
    action: ClassVar[str] = "ping"
    target: str
    count: int = 5


class PingResult(BaseModel):
    sent: int
    received: int
