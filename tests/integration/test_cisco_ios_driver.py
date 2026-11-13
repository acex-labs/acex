"""Which Cisco assets the CLI driver takes on."""

import pytest
from acex_devkit.models.asset import Asset
from acex_devkit.models.platform import OS, Vendor
from acex_driver_cisco_ioscli.cisco_ios_cli import CiscoIOSCLIDriver


def cisco_asset(os: OS) -> Asset:
    return Asset(vendor=Vendor.cisco, serial_number="FOC0001", os=os, hardware_model="C9300-24P")


@pytest.mark.parametrize("os", [OS.cisco_ios, OS.cisco_iosxe])
def test_driver_takes_ios_and_iosxe_assets(os):
    assert CiscoIOSCLIDriver().supports(cisco_asset(os))


@pytest.mark.parametrize("os", [OS.cisco_nxos, OS.cisco_iosxr])
def test_driver_leaves_other_cisco_operating_systems_alone(os):
    assert not CiscoIOSCLIDriver().supports(cisco_asset(os))


def test_platforms_are_listed_in_the_driver_capabilities():
    declared = {(p.vendor, p.os) for p in CiscoIOSCLIDriver().capabilities.platforms}
    assert declared == {(Vendor.cisco, OS.cisco_ios), (Vendor.cisco, OS.cisco_iosxe)}
