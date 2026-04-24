"""Driver base classes for ACE-X network element drivers."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from acex_devkit.models.node_response import NodeListItem
from acex_devkit.models.management_connection import ManagementConnection


class ParserBase(ABC):
    """Base class for configuration parsers."""
    
    @abstractmethod
    def parse(self, configuration: str) -> Any:
        """Parse device configuration into a structured model.
        
        Args:
            configuration: Raw configuration string from device
            
        Returns:
            Parsed configuration model
        """
        pass


class RendererBase(ABC):
    """Base class for configuration renderers."""
    
    @abstractmethod
    def render(self, model: Dict[str, Any], asset: Any = None) -> Any:
        """Render configuration model to device-specific format.
        
        Args:
            model: Device-agnostic configuration model
            asset: Optional asset context
            
        Returns:
            Device-specific configuration (e.g., string, XML tree)
        """
        pass


class TransportBase(ABC):
    """Base class for device transport/communication.

    Each method is self-contained — the driver decides internally
    whether to open/close sessions per call, pool connections, or
    make stateless requests.

    Args:
        node: The node instance (identity, hostname, vendor, os, ned_id)
        connection: Management connection (target_ip, connection_type)
        **kwargs: Future use (credentials, options, etc.)
    """

    @abstractmethod
    def get_config(self, node: NodeListItem, connection: ManagementConnection, **kwargs) -> str:
        """Fetch the full running configuration from a device."""
        pass

    @abstractmethod
    def send_config(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> str:
        """Apply configuration commands to a device."""
        pass

    def execute(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> list[str]:
        """Run arbitrary commands and return output per command. Opt-in per driver."""
        raise NotImplementedError(f"{self.__class__.__name__} does not implement execute()")


class NetworkElementDriver:
    """Base class for network element drivers.
    
    Combines renderer, transport, and parser to provide complete
    configuration management for network devices.
    
    Attributes:
        renderer_class: Renderer class to use (must be set in subclass)
        transport_class: Transport class to use (must be set in subclass)
        parser_class: Parser class to use (must be set in subclass)
    """
    
    renderer_class = None
    transport_class = None
    parser_class = None

    def __init__(self):
        """Initialize driver with renderer, transport, and parser instances."""
        if self.renderer_class is None or self.transport_class is None or self.parser_class is None:
            raise NotImplementedError(
                "renderer_class, transport_class, and parser_class must be set in subclass"
            )
        self.renderer = self.renderer_class()
        self.transport = self.transport_class()
        self.parser = self.parser_class()

    @abstractmethod
    def render(self, logical_node: "LogicalNode", asset: Any = None) -> Any:
        """Render logical node to device configuration.
        
        Args:
            logical_node: Logical node containing configuration
            asset: Optional asset context
            
        Returns:
            Rendered configuration
        """
        return self.renderer.render(logical_node.model_dump(), asset)

    @abstractmethod
    def parse(self, configuration: str) -> Any:
        """Parse device configuration.
        
        Args:
            configuration: Raw device configuration
            
        Returns:
            Parsed configuration model
        """
        return self.parser.parse(configuration)
