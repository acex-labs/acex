"""How Cisco IOS names a physical port at a position on a node's hardware."""

import logging
import re
from typing import Any

from acex_devkit import device_types
from acex_devkit.models.device_type import InterfaceSlot, Speed
from acex_devkit.models.node_response import NodeInstance

log = logging.getLogger(__name__)


class CiscoInterfaceNaming:
    """Names a physical port from its position — stack member, module, index — on the node's hardware,
    and reads the position back from a name.

    Positions are zero-based like devkit's `InterfaceSlot`; IOS numbers stack members and ports from
    one. Stackable hardware names ports `{prefix}{member}/{module}/{port}`, other hardware
    `{prefix}{module}/{port}`. The prefix follows the port's speed: the configured `speed` when set,
    otherwise the fastest the port supports. A cluster's members are stacked in the cluster's order.
    """

    PREFIXES = {
        Speed.fast_ethernet: "FastEthernet",
        Speed.gigabit: "GigabitEthernet",
        Speed.two_and_half_gigabit: "TwoGigabitEthernet",
        Speed.five_gigabit: "FiveGigabitEthernet",
        Speed.ten_gigabit: "TenGigabitEthernet",
        Speed.twentyfive_gigabit: "TwentyFiveGigE",
        Speed.forty_gigabit: "FortyGigabitEthernet",
        Speed.hundred_gigabit: "HundredGigE",
        Speed.fourhundred_gigabit: "FourHundredGigE",
    }
    SPEEDS = {prefix: int(speed) for speed, prefix in PREFIXES.items()}
    NAME = re.compile(r"(?P<prefix>[A-Za-z]+)(?P<numbers>\d+(?:/\d+){1,2})")

    def __init__(self, node: NodeInstance | None):
        self.known = node is not None
        """Without a node there's no hardware to name ports from; they keep the name the model gives."""
        self.slots: dict[tuple[int, int, int], InterfaceSlot] = {}
        self.stackable = True
        for stack_index, asset in self.members(node):
            device = device_types.get(asset.hardware_model)
            if device is None:
                log.warning(f"{asset.hardware_model} is not a declared device type, so its ports can't be named")
                continue
            self.stackable = device.stackable
            for slot in device.interfaces():
                self.slots[(stack_index, slot.module_index, slot.index)] = slot

    @staticmethod
    def members(node: NodeInstance | None) -> list[tuple[int, Any]]:
        if node is None:
            return []
        if node.asset.type == "asset_cluster":
            return list(enumerate(node.asset.assets))
        return [(0, node.asset)]

    def name(self, values: dict[str, Any]) -> str | None:
        """The port's name, or None when the hardware has no port at its position."""
        stack, module, index = values.get("stack_index") or 0, values.get("module_index") or 0, values["index"]
        slot = self.slots.get((stack, module, index))
        if slot is None:
            log.info(f"no port at stack {stack}, module {module}, index {index} on this hardware; not rendered")
            return None
        prefix = self.PREFIXES.get(values.get("speed") or max(slot.speed_capabilities))
        if prefix is None:
            log.warning(f"no Cisco interface prefix for speed {values.get('speed')}; port {index} not rendered")
            return None
        return prefix + (f"{stack + 1}/{module}/{index + 1}" if self.stackable else f"{module}/{index + 1}")

    def position(self, name: str) -> dict[str, Any] | None:
        """The position fields a port name stands for, or None for a name that isn't a physical port.
        `speed` is only set when the prefix differs from the port's fastest, mirroring `name`."""
        match = self.NAME.fullmatch(name)
        if match is None or match["prefix"] not in self.SPEEDS:
            return None
        numbers = [int(n) for n in match["numbers"].split("/")]
        stack, module, port = (numbers[0] - 1, *numbers[1:]) if len(numbers) == 3 else (0, *numbers)
        if port < 1 or stack < 0:
            return None  # ports number from 1; a 0 is the management port (GigabitEthernet0/0), not front panel
        fields: dict[str, Any] = {"module_index": module, "index": port - 1}
        if stack:
            fields["stack_index"] = stack
        speed = self.SPEEDS[match["prefix"]]
        slot = self.slots.get((stack, module, port - 1))
        if slot is None or speed != max(slot.speed_capabilities):
            fields["speed"] = speed
        return fields
