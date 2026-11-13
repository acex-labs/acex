import contextlib

import pytest
from acex_driver_waystream_ibos.transport import IbosTransport

from ibos_kit.mock.server import build


@pytest.fixture
def mock(monkeypatch):
    # `async with mock("b") as running:` starts a mock of a scenario and points the transport at it.
    @contextlib.asynccontextmanager
    async def start(scenario: str, **overrides):
        async with build(scenario, **overrides) as running:
            monkeypatch.setattr(IbosTransport, "PORT", running.port)
            yield running

    return start
