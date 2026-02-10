"""Type definitions and protocols for ACE-X DevKit."""

from typing import Protocol, Any, Dict, runtime_checkable


@runtime_checkable
class Renderable(Protocol):
    """Protocol for objects that can be rendered to configuration."""
    
    def render(self, model: Dict[str, Any], asset: Any = None) -> Any:
        """Render configuration."""
        ...


@runtime_checkable
class Parseable(Protocol):
    """Protocol for objects that can parse configuration."""
    
    def parse(self, configuration: str) -> Any:
        """Parse configuration."""
        ...


@runtime_checkable
class Transportable(Protocol):
    """Protocol for objects that can transport configuration."""
    
    def connect(self) -> None:
        """Connect to device."""
        ...
    
    def send(self, payload: Any) -> None:
        """Send configuration."""
        ...
    
    def verify(self) -> bool:
        """Verify configuration."""
        ...
    
    def rollback(self) -> None:
        """Rollback configuration."""
        ...
