"""The interface every model adapter implements."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from ..types import StreamEvent, Turn


class ModelAdapter(ABC):
    """Speaks one wire protocol to one endpoint.

    An adapter translates a Turn into its protocol's request and the response
    back into StreamEvents: text as it streams, then the round's tool calls,
    any state it needs back next round, and usage. Failures are raised as
    ProviderError, never as an SDK's own exception.
    """

    @abstractmethod
    def stream(self, turn: Turn) -> AsyncIterator[StreamEvent]:
        """Run one round and stream what the model produces."""

    @abstractmethod
    async def list_models(self) -> list[dict]:
        """The endpoint's model listing, one raw dict per model."""
