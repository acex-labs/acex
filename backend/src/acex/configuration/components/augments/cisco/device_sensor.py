"""Cisco IOS / IOS-XE device-sensor augments."""

from typing import List, Literal, Optional
from dataclasses import dataclass, field

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.services import Services

from acex_devkit.models.composed_configuration import AugmentAttributes


class CiscoDeviceSensorFilterListAttributes(AugmentAttributes):
    type: Literal["cisco_device_sensor_filter_list"] = "cisco_device_sensor_filter_list"
    name: str
    protocol: str  # lldp | dhcp | cdp


class CiscoDeviceSensorFilterList(Augment):
    """Named device-sensor filter-list for a given protocol."""
    type = "cisco_device_sensor_filter_list"
    model_cls = CiscoDeviceSensorFilterListAttributes
    valid_targets = (Services,)
    default_vendor = "cisco"
    singleton = False


class CiscoDeviceSensorFilterSpecAttributes(AugmentAttributes):
    type: Literal["cisco_device_sensor_filter_spec"] = "cisco_device_sensor_filter_spec"
    protocol: str  # lldp | dhcp | cdp
    filter_list_name: str


class CiscoDeviceSensorFilterSpec(Augment):
    """device-sensor filter-spec <protocol> include list <name>."""
    type = "cisco_device_sensor_filter_spec"
    model_cls = CiscoDeviceSensorFilterSpecAttributes
    valid_targets = (Services,)
    default_vendor = "cisco"
    singleton = False

    def pre_init(self):
        fl = self.kwargs.get("filter_list")
        if isinstance(fl, CiscoDeviceSensorFilterList):
            self.kwargs["filter_list_name"] = fl.kwargs.get("name", "")
            if "protocol" not in self.kwargs:
                self.kwargs["protocol"] = fl.kwargs.get("protocol", "")
            self.kwargs.setdefault("name", fl.kwargs.get("protocol", ""))
            del self.kwargs["filter_list"]
        super().pre_init()


class CiscoDeviceSensorNotifyAttributes(AugmentAttributes):
    type: Literal["cisco_device_sensor_notify"] = "cisco_device_sensor_notify"
    all_changes: bool = True


class CiscoDeviceSensorNotify(Augment):
    """device-sensor notify all-changes."""
    type = "cisco_device_sensor_notify"
    model_cls = CiscoDeviceSensorNotifyAttributes
    valid_targets = (Services,)
    default_vendor = "cisco"
