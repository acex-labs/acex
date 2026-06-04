from abc import ABC, abstractmethod


class AuthProvider(ABC):
    @abstractmethod
    def get_token(self) -> str:
        """Return a valid Bearer token, refreshing if necessary."""
        ...
