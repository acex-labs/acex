

from abc import ABC, abstractmethod
from .integration_plugin_base import IntegrationPluginBase


class IntegrationPluginFactoryBase(ABC):
    """
    Gemensam basklass för alla plugin-factories.
    """
    @abstractmethod
    def create_plugin(self, **kwargs) -> IntegrationPluginBase:
        """Skapa och returnera en instans av plugin."""
        pass
