import pytest
from acex_devkit.exceptions import DriverException
from acex_devkit.models.asset import Asset
from acex_devkit.models.platform import OS, Vendor
from acex_devkit.models.state import DeviceFacts
from acex_driver_waystream_ibos import WaystreamIbosDriver
from acex_driver_waystream_ibos.state import IbosFacts, IbosState, parse_show_version, read_facts
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


needs_devkit = pytest.mark.skipif(
    not hasattr(Vendor, "waystream"), reason="the devkit has no Waystream yet: merge dev, which has acex PR 386"
)


@needs_devkit
def test_the_driver_declares_the_waystream_platform_and_only_that():
    driver = WaystreamIbosDriver()
    assert [(p.vendor, p.os) for p in driver.capabilities.platforms] == [(Vendor.waystream, OS.waystream_ibos)]
    waystream = Asset(vendor=Vendor.waystream, serial_number="SN1", os=OS.waystream_ibos, hardware_model="MS4026-AC")
    cisco = Asset(vendor=Vendor.cisco, serial_number="SN2", os=OS.cisco_iosxe, hardware_model="C9300-24T")
    assert driver.supports(waystream)
    assert not driver.supports(cisco)


@needs_devkit
async def test_get_facts_returns_the_facts_in_the_form_the_devkit_wants(mock):
    async with mock("d"), opened([USERPASS, ENABLE]) as transport:
        facts = await IbosState().get_facts(transport)
    assert facts == DeviceFacts(
        vendor=Vendor.waystream,
        os=OS.waystream_ibos,
        os_version="6.3.0-ED-R",
        hardware_model="MS4026-AC",
        serial_number="0008AE00D004",
    )
    assert "get_facts" in IbosState.implemented()
