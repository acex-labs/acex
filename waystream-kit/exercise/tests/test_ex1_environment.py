import socket

from ibos_kit.mock.scenarios import SCENARIOS
from ibos_kit.mock.server import build


async def test_the_mock_starts_on_loopback_and_accepts_a_tcp_connection():
    async with build("b") as running:
        assert running.host == "127.0.0.1"
        with socket.create_connection((running.host, running.port), timeout=5):
            pass


def test_the_scenarios_of_the_guide_exist():
    assert {"a-asr6000-635", "b-ms4000-635", "c-ms4000-635-client", "d-ms4000-630", "e-ms7048-762"} <= set(SCENARIOS)


def test_the_driver_package_imports():
    import acex_driver_waystream_ibos  # noqa: F401
