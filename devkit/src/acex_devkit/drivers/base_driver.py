from abc import ABC, abstractmethod
from typing import Any, Dict

class ParserBase(ABC):
    @abstractmethod
    def parse(self, model: Dict[str, Any]) -> Any:
        """Parsar running-config"""

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
    parser_class = None

    def __init__(self):
        if self.renderer_class is None or self.transport_class is None or self.parser_class is None:
            raise NotImplementedError("renderer_class and transport_class must be set in subclass")
        self.renderer = self.renderer_class()
        self.transport = self.transport_class()
        self.parser = self.parser_class()

    @abstractmethod
    def render(self, configuration: ComposedConfiguration, asset: "Asset") -> Any:
        """Render configuration from composedconfig and asset."""
        pass

    @abstractmethod
    def parse(self, configuration: str) -> ComposedConfiguration:
        """
        Parse observed configuration into a composedconfiguration object.
        """

    
