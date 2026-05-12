"""
Cisco Device Sensor augment.

Models ``device-sensor filter-list``, ``device-sensor filter-spec``, and
``device-sensor notify`` commands.  Renders to::

    device-sensor filter-list lldp list my_lldp_list
     tlv name system-name
     tlv name system-description
    !
    device-sensor filter-spec lldp include list my_lldp_list
    device-sensor notify all-changes

All filter-lists, filter-specs, and the notify flag are held in a single
augment instance so the entire device-sensor block is self-contained.
"""

from typing import Dict, Literal, Optional

from pydantic import BaseModel

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.services import ServicesConfig
from acex_devkit.models import AttributeValue
from acex_devkit.models.composed_configuration import AugmentAttributes

# -- nested payload models -------------------------------------------------


class DeviceSensorFilterItem(BaseModel):
    """Single TLV or option entry (``tlv name X`` / ``option name X``)."""

    name: AttributeValue[str]


class DeviceSensorFilterList(BaseModel):
    """``device-sensor filter-list {protocol} list {list_name}``."""

    name: AttributeValue[str]
    protocol: AttributeValue[str]  # lldp | dhcp | cdp
    items: Dict[str, DeviceSensorFilterItem] = {}


class DeviceSensorFilterSpec(BaseModel):
    """``device-sensor filter-spec {protocol} {action} list {list_name}``."""

    protocol: AttributeValue[str]  # lldp | dhcp | cdp
    action: AttributeValue[str]  # include | exclude
    filter_list: AttributeValue[str]  # name of the referenced filter-list


# -- augment attribute model -----------------------------------------------


class CiscoDeviceSensorAttributes(AugmentAttributes):
    """Full device-sensor configuration block."""

    type: Literal["cisco.device_sensor"] = "cisco.device_sensor"
    filter_lists: Dict[str, DeviceSensorFilterList] = {}
    filter_specs: Dict[str, DeviceSensorFilterSpec] = {}
    notify: Optional[AttributeValue[str]] = None  # e.g. "all-changes"


# -- augment component -----------------------------------------------------


class CiscoDeviceSensor(Augment):
    """
    Cisco device-sensor augment, targets ``ServicesConfig``.

    Integrator kwargs (transformed by ``pre_init``):

    * **filter_lists** -- ``dict[str, dict]`` keyed by list name::

          {"my_lldp_list": {"protocol": "lldp", "items": ["system-name", ...]}}

    * **filter_specs** -- ``dict[str, dict]`` keyed by an arbitrary label::

          {"lldp_spec": {"protocol": "lldp", "action": "include",
                         "filter_list": "my_lldp_list"}}

    * **notify** -- ``str | None`` e.g. ``"all-changes"``
    """

    type = "cisco.device_sensor"
    model_cls = CiscoDeviceSensorAttributes
    default_vendor = "cisco"
    valid_targets = (ServicesConfig,)

    def pre_init(self):
        # Expand shorthand filter_lists: items list[str] -> Dict[str, model]
        raw_lists = self.kwargs.get("filter_lists")
        if isinstance(raw_lists, dict):
            expanded = {}
            for list_name, cfg in raw_lists.items():
                items_raw = cfg.get("items", [])
                items = (
                    {item: {"name": item} for item in items_raw}
                    if isinstance(items_raw, list)
                    else items_raw
                )
                expanded[list_name] = {
                    "name": list_name,
                    "protocol": cfg["protocol"],
                    "items": items,
                }
            self.kwargs["filter_lists"] = expanded

        # Let Augment.pre_init handle target extraction
        super().pre_init()
