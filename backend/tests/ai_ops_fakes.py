"""Test doubles for the AI Ops provider layer."""

from acex.ai_ops import AIOpsManager
from acex.ai_ops.adapters import ModelAdapter
from acex.ai_ops.config import AIChainLevel, AIOpsSettings, AIProvider


class FakeAdapter(ModelAdapter):
    """Plays back scripted rounds. A round is a list of events (an Exception in
    it is raised at that point) or an Exception raised before the first event."""

    def __init__(self, *rounds, models: list[dict] | Exception | None = None):
        self.rounds = list(rounds)
        self.turns = []
        self.models = models if models is not None else []

    async def stream(self, turn):
        self.turns.append(turn)
        step = self.rounds.pop(0)
        if isinstance(step, Exception):
            raise step
        for event in step:
            if isinstance(event, Exception):
                raise event
            yield event

    async def list_models(self):
        if isinstance(self.models, Exception):
            raise self.models
        return self.models


class FakeEndpoints:
    """Hands out one FakeAdapter per provider."""

    def __init__(self, adapters: dict[str, FakeAdapter]):
        self.adapters = adapters

    def adapter(self, provider, model_id):
        return self.adapters[provider.name]

    def listing_adapter(self, provider):
        return self.adapters[provider.name]


def manager(*, chain=("p1/m1", "p2/m2"), providers=None, mcp_server_url=None, **adapters) -> AIOpsManager:
    """An AIOpsManager whose providers are FakeAdapters (p1, p2 by default)."""
    settings = AIOpsSettings(
        providers=providers
        or {"p1": AIProvider(base_url="http://1", api_key="k"), "p2": AIProvider(base_url="http://2", api_key="k")},
        chains={"default": [AIChainLevel.parse(level) for level in chain]},
        mcp_server_url=mcp_server_url,
    )
    m = AIOpsManager(settings)
    endpoints = FakeEndpoints({name: adapters.get(name) or FakeAdapter() for name in settings.providers})
    m.endpoints = m.catalog.endpoints = m.router.endpoints = endpoints
    return m
