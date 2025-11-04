from abc import ABC, abstractmethod
from acex.exceptions import MethodNotImplemented


class IntegrationPluginBase(ABC):
    """
    Basklass för alla datakälls-plugins.
    Stöd för metadata, enkel registrering och tydligt interface.
    """
    # Metadata: Ange vilka objektstyper denna plugin gäller för
    RESOURCE_TYPES = []
    DATA_TYPES = []

    @abstractmethod
    def query(self, *args, **kwargs):
        """Hämta data från datakällan. Måste implementeras av plugin."""
        raise MethodNotImplemented("query() måste implementeras i plugin.")

    @property
    def capabilities(self):
        caps = {}
        for attr_name in dir(self):
            if attr_name == "capabilities":
                continue
            attr = getattr(self, attr_name)
            if callable(attr) and not attr_name.startswith("__"):
                func = getattr(attr, "__func__", attr)
                caps[attr_name] = func
        return caps
