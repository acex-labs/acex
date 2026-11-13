import pytest
from acex_devkit.exceptions import ConnectionError, DriverException
from ibos_helpers import ENABLE, USERPASS, opened

from ibos_kit.paths import DEVICE_FIXTURES


def fixture(path: str) -> str:
    return (DEVICE_FIXTURES / path).read_text().rstrip("\n")


@pytest.mark.parametrize(
    ("scenario", "path"),
    [("a", "asr6000-6.3.5/running-config.txt"), ("b", "ms4000-6.3.5/running-config.txt")],
)
async def test_get_config_returns_the_running_configuration_exactly_as_printed(mock, scenario, path):
    async with mock(scenario), opened() as transport:
        config = await transport.get_config()
    assert config == fixture(path)
    assert "\r" not in config


async def test_get_config_keeps_the_volatile_lines_because_raw_is_raw(mock):
    async with mock("c"), opened() as transport:
        config = await transport.get_config()
    assert config == fixture("ms4000-6.3.5/running-config.with-client.txt")
    assert "!volatile" in config


async def test_get_config_works_on_the_device_that_needs_enable_first(mock):
    async with mock("d"), opened([USERPASS, ENABLE]) as transport:
        assert (await transport.get_config()).startswith("! version ibos-ms4k-6.3.0-ED-R")
    async with mock("e"), opened() as transport:
        assert (await transport.get_config()).startswith("! version ibos-cma-7.6.2-GD-R")


async def test_an_error_answer_is_raised_and_never_returned_as_a_configuration(mock):
    async with mock("e-ms7048-762-never"), opened() as transport:
        with pytest.raises(DriverException, match="Invalid command"):
            await transport.get_config()


async def test_a_connection_that_drops_in_the_middle_is_an_error_not_a_short_configuration(mock):
    async with mock("f", drop_after_lines=4):
        with pytest.raises(ConnectionError):
            async with opened() as transport:
                await transport.get_config()


async def test_get_config_can_be_called_again_on_the_same_session(mock):
    async with mock("b"), opened() as transport:
        assert await transport.get_config() == await transport.get_config()
