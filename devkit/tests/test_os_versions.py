"""Every OS must declare a version scheme, and every scheme must hold."""

import pytest
from acex_devkit.models.asset import Asset
from acex_devkit.models.os_version import OsVersionScheme
from acex_devkit.models.platform import OS, Vendor


def test_every_os_declares_a_scheme():
    """Asset rejects a version it cannot check, so no OS may be left undeclared."""
    missing = [os.value for os in OS if OsVersionScheme.for_os(os) is None]
    assert not missing, f"OS without a declared version scheme: {missing}"


@pytest.mark.parametrize("os", list(OS))
def test_declared_examples_are_accepted(os):
    scheme = OsVersionScheme.for_os(os)
    assert scheme.examples, f"{os.value} declares no examples"
    for example in scheme.examples:
        assert scheme.accepts(example)


@pytest.mark.parametrize("os", list(OS))
def test_examples_round_trip_through_asset(os):
    scheme = OsVersionScheme.for_os(os)
    for example in scheme.examples:
        asset = Asset(
            vendor=Vendor.cisco,
            serial_number="SN1",
            os=os,
            hardware_model="x",
            os_version=example,
        )
        assert asset.os_version == example


def test_junk_is_rejected():
    scheme = OsVersionScheme.for_os(OS.cisco_iosxe)
    for junk in ["nonsense", "17.9", "", "   "]:
        with pytest.raises(ValueError):
            scheme.check(junk)


def test_ordering_is_semantic():
    """String sorting gets 17.9 vs 17.12 and 9.3 vs 10.2 wrong; the scheme must not."""
    scheme = OsVersionScheme.for_os(OS.cisco_iosxe)
    versions = [scheme.normalize(v) for v in ["17.12.3a", "17.9.4", "16.12.5b", "17.9.4a"]]
    assert [str(v) for v in sorted(versions)] == ["16.12.5b", "17.9.4", "17.9.4a", "17.12.3a"]


def test_undiscovered_asset_needs_no_version():
    asset = Asset(vendor=Vendor.juniper, serial_number="JN1", os=OS.juniper_junos, hardware_model="EX4400-24X")
    assert asset.os_version is None
