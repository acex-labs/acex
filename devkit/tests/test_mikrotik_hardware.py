"""MikroTik is a vendor the platform catalog offers, with the RouterBOARDs declared so far running RouterOS."""

import pytest
from acex_devkit import device_types
from acex_devkit.models.asset import Asset
from acex_devkit.models.device_type import PortMedia, Speed
from acex_devkit.models.platform import OS, Vendor


def test_mikrotik_is_among_the_vendors_the_catalog_offers():
    assert Vendor.mikrotik in device_types.vendors()


def test_every_mikrotik_model_runs_routeros_and_does_not_stack():
    declared = device_types.device_types(vendor=Vendor.mikrotik)

    assert declared
    assert all(d.os == [OS.mikrotik_routeros] and not d.stackable for d in declared)


@pytest.mark.parametrize(
    ("model", "primary", "ports"),
    [
        ("RB5009UG+S+IN", "RB5009UG+S+IN", 9),
        ("rb5009ug+s+in", "RB5009UG+S+IN", 9),
        ("hEX", "RB750Gr3", 5),
        ("hEX S", "RB760iGS", 6),
        ("RB4011iGS+RM", "RB4011iGS+RM", 11),
        ("CCR2004-16G-2S+", "CCR2004-16G-2S+", 18),
        ("CRS326-24G-2S+RM", "CRS326-24G-2S+RM", 26),
    ],
)
def test_a_model_is_found_by_the_name_it_goes_by_and_has_the_ports_of_its_product_page(model, primary, ports):
    device = device_types.get(model)

    assert device.primary_model == primary
    assert len(device.interfaces()) == ports


def test_the_ports_of_an_rb5009_come_in_the_order_of_the_product_page():
    slots = device_types.get("RB5009UG+S+IN").interfaces()

    assert (slots[0].media, slots[0].speed_capabilities) == (PortMedia.rj45, [Speed.two_and_half_gigabit])
    assert {(s.media, tuple(s.speed_capabilities)) for s in slots[1:8]} == {(PortMedia.rj45, (Speed.gigabit,))}
    assert (slots[8].media, slots[8].speed_capabilities) == (PortMedia.sfp_plus, [Speed.ten_gigabit])


def test_an_asset_can_be_a_routerboard_on_routeros():
    asset = Asset(
        vendor=Vendor.mikrotik,
        serial_number="HF909ABC123",
        os=OS.mikrotik_routeros,
        hardware_model="RB5009UG+S+IN",
        os_version="7.17",
    )

    assert (asset.vendor, asset.os, asset.os_version) == (Vendor.mikrotik, OS.mikrotik_routeros, "7.17")
