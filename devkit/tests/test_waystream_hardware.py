"""Waystream is a vendor the platform catalog offers, with the two switches seen on a device so far."""

import pytest
from acex_devkit import device_types
from acex_devkit.models.asset import Asset
from acex_devkit.models.os_version import OsVersionScheme
from acex_devkit.models.platform import OS, Vendor


def test_waystream_is_among_the_vendors_the_catalog_offers():
    assert Vendor.waystream in device_types.vendors()


def test_every_waystream_model_runs_ibos_and_does_not_stack():
    declared = device_types.device_types(vendor=Vendor.waystream)

    assert {m for d in declared for m in d.models} == {"MS4026-AC", "MS7048-AC"}
    assert all(d.os == [OS.waystream_ibos] and not d.stackable for d in declared)


@pytest.mark.parametrize("model", ["MS4026-AC", "ms4026-ac", "MS7048-AC"])
def test_a_model_is_found_whatever_the_case(model):
    assert device_types.get(model).primary_model == model.upper()


@pytest.mark.parametrize(
    ("model", "version"),
    [
        ("MS4026-AC", "6.3.0-ED-R"),
        ("MS4026-AC", "6.3.5-ED-R"),
        ("MS7048-AC", "7.5.2-ED-R"),
        ("MS7048-AC", "7.6.2-GD-R"),
    ],
)
def test_an_asset_can_be_a_switch_on_a_firmware_seen_in_the_field(model, version):
    asset = Asset(
        vendor=Vendor.waystream,
        serial_number="0008AE00D004",
        os=OS.waystream_ibos,
        hardware_model=model,
        os_version=version,
    )

    assert (asset.hardware_model, asset.os_version) == (model, version)
    assert OsVersionScheme.for_os(OS.waystream_ibos).accepts(version)
