"""The Catalyst 1300 models are declared on Cisco Business firmware, with the ports of their data sheet."""

import pytest
from acex_devkit import device_types
from acex_devkit.models.device_type import PortMedia, Speed
from acex_devkit.models.platform import OS, Vendor


def test_every_catalyst_1300_model_runs_cisco_business_firmware():
    declared = device_types.device_types(os=OS.cisco_business)

    assert {d.primary_model for d in declared} == {
        "C1300-8P-E-2G",
        "C1300-24P-4X",
        "C1300-48P-4X",
        "C1300-48P-4G",
        "C1300-48T-4G",
    }
    assert all(d.vendor == Vendor.cisco and d.os == [OS.cisco_business] for d in declared)


def test_no_other_cisco_model_is_declared_on_cisco_business_firmware():
    on_ios = {d.primary_model for d in device_types.device_types(os=OS.cisco_ios)}
    on_ios_xe = {d.primary_model for d in device_types.device_types(os=OS.cisco_iosxe)}

    assert not any(model.startswith("C1300") for model in on_ios | on_ios_xe)


@pytest.mark.parametrize(
    ("model", "copper", "uplinks", "uplink_media", "uplink_speed"),
    [
        ("C1300-8P-E-2G", 8, 2, PortMedia.sfp, Speed.gigabit),
        ("C1300-24P-4X", 24, 4, PortMedia.sfp_plus, Speed.ten_gigabit),
        ("C1300-48P-4X", 48, 4, PortMedia.sfp_plus, Speed.ten_gigabit),
        ("C1300-48P-4G", 48, 4, PortMedia.sfp, Speed.gigabit),
        ("C1300-48T-4G", 48, 4, PortMedia.sfp, Speed.gigabit),
    ],
)
def test_a_model_has_the_ports_of_its_data_sheet(model, copper, uplinks, uplink_media, uplink_speed):
    slots = device_types.get(model).interfaces()

    assert len(slots) == copper + uplinks
    assert {(s.media, tuple(s.speed_capabilities)) for s in slots[:copper]} == {(PortMedia.rj45, (Speed.gigabit,))}
    assert {(s.media, tuple(s.speed_capabilities)) for s in slots[copper:]} == {(uplink_media, (uplink_speed,))}


def test_a_model_is_found_whatever_the_case():
    assert device_types.get("c1300-48p-4x").primary_model == "C1300-48P-4X"
