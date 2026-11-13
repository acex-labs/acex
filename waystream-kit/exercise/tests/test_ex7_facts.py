import pytest
from acex_devkit.exceptions import DriverException
from acex_driver_waystream_ibos.state import IbosFacts, parse_show_version, read_facts
from ibos_helpers import ENABLE, USERPASS, opened

from ibos_kit.paths import DEVICE_FIXTURES

CASES = [
    (
        "ms4000-6.3.0/show-version.txt",
        IbosFacts("ms-lab-04", "6.3.0-ED-R", "ibos-ms4k-6.3.0-ED-R", "MS4026-AC", "0008AE00D004"),
    ),
    (
        "ms7048-7.6.2/show-version.txt",
        IbosFacts(None, "7.6.2-GD-R", "ibos-cma-7.6.2-GD-R", "MS7048-AC", "0008AE00E001"),
    ),
    (
        "asr6000-6.3.5/show-version.assumed.txt",
        IbosFacts("asr-lab-01", "6.3.5-ED-R", "ibos-asr6k-6.3.5-ED-R", "ASR6000", "0008AE00A001"),
    ),
]


@pytest.mark.parametrize(("path", "facts"), CASES)
def test_the_facts_come_out_of_show_version(path, facts):
    assert parse_show_version((DEVICE_FIXTURES / path).read_text()) == facts


def test_missing_lines_give_none_instead_of_an_exception():
    assert parse_show_version("Intelligent Broadband Operating System (iBOS), Version 6.3.0-ED-R\n") == IbosFacts(
        os_version="6.3.0-ED-R"
    )
    assert parse_show_version("") == IbosFacts()


def test_an_error_answer_is_not_facts():
    with pytest.raises(DriverException):
        parse_show_version("%-ERR: show version\n            ^^^^^^^ Invalid command")


async def test_read_facts_asks_the_device(mock):
    async with mock("d"), opened([USERPASS, ENABLE]) as transport:
        facts = await read_facts(transport)
    assert facts.hardware_model == "MS4026-AC" and facts.os_version == "6.3.0-ED-R"
