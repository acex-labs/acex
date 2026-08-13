from abc import ABC, abstractmethod


class AuthProvider(ABC):
    @abstractmethod
    def get_token(self) -> str:
        """Return a valid Bearer token, refreshing if necessary."""
        ...


class NullAuthProvider(AuthProvider):
    """No-op auth provider for backends with auth disabled.

    Returns an empty token; `_BearerAuth` in RestClient skips the
    Authorization header when the token is empty.
    """

    def get_token(self) -> str:
        return ""


__all__ = ["AuthProvider", "NullAuthProvider"]
