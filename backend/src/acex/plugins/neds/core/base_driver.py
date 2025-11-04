from abc import ABC, abstractmethod
from typing import Any, Dict

from acex.models import LogicalNode

class RendererBase(ABC):
    @abstractmethod
    def render(self, model: Dict[str, Any]) -> Any:
        """Tar en device‑agnostisk konfigurationsmodell och returnerar
        en transport‑specifik representation (t.ex. string, XML‑tree…)."""

class TransportBase(ABC):
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def send(self, payload: Any) -> None: ...

    @abstractmethod
    def verify(self) -> bool: ...

    @abstractmethod
    def rollback(self) -> None: ...

class NetworkElementDriver:
    """Kombinerar renderer + transport – exponeras som en plugin."""
    renderer_class = None
    transport_class = None

    def __init__(self):
        if self.renderer_class is None or self.transport_class is None:
            raise NotImplementedError("renderer_class and transport_class must be set in subclass")
        self.renderer = self.renderer_class()
        self.transport = self.transport_class()

    @property
    def key(self) -> str:
        """Returnerar en unik identifierare för denna driver."""

        name = getattr(self.__class__, "name", self.__class__.__name__.lower())

        return f"{name}:{self.__class__.version.lower()}"

    @abstractmethod
    def render(self, logical_node:LogicalNode) -> Any:
        """Tar en LogicalNode och returnerar en konfigurationsrepresentation."""
        return self.renderer.render(logical_node.model_dump())


    # def apply(self, model: Dict[str, Any]) -> None:
    #     cfg = self.renderer.render(model)
    #     self.transport.connect()
    #     self.transport.send(cfg)
    #     if not self.transport.verify():
    #         self.transport.rollback()
    #         raise RuntimeError("Verification failed – rollback executed")