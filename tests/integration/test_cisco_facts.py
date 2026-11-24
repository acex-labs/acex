"""What the two Cisco drivers read out of `show version`: the serial number, hardware model, OS and version that ZTP
discovery reports and an asset is created from. Each platform words it differently."""

import asyncio

import pytest
from acex_devkit.models.platform import OS, Vendor
from acex_driver_cisco_ios_classic_cli.state import CiscoIOSState as ClassicState
from acex_driver_cisco_ioscli.state import CiscoIOSState as XeState

CATALYST_9300 = """\
Cisco IOS XE Software, Version 17.09.04a
Cisco IOS Software [Cupertino], Catalyst L3 Switch Software (CAT9K_IOSXE), Version 17.9.4a, RELEASE SOFTWARE (fc3)
cisco C9300-24P (X86) processor with 1392628K/6147K bytes of memory.
Processor board ID FOC2345L0AB
Model Number                       : C9300-24P
System Serial Number               : FOC2345L0AB
"""

ISR_4331 = """\
Cisco IOS XE Software, Version 16.09.04
Cisco IOS Software [Fuji], ISR Software (X86_64_LINUX_IOSD-UNIVERSALK9-M), Version 16.9.4, RELEASE SOFTWARE (fc2)
cisco ISR4331/K9 (1RU) processor with 1795979K/6147K bytes of memory.
Processor board ID FDO21360ABC
"""

# Lowercase "Model number" and "System serial number": the Catalyst 3560CX on classic IOS has no uppercase lines.
CATALYST_3560CX = """\
Cisco IOS Software, C3560CX Software (C3560CX-UNIVERSALK9-M), Version 15.2(7)E13, RELEASE SOFTWARE (fc2)
cisco WS-C3560CX-12PC-S (APM86XXX) processor (revision A0) with 524288K bytes of memory.
Processor board ID FOC1949Y0AB
Model number                        : WS-C3560CX-12PC-S
System serial number                : FOC1949Y0AB
"""

# An ISR G2 router names its model right after "Cisco", and has no processor on that line.
ISR_1941 = """\
Cisco IOS Software, C1900 Software (C1900-UNIVERSALK9-M), Version 15.7(3)M9, RELEASE SOFTWARE (fc1)
Cisco CISCO1941/K9 (revision 1.0) with 487424K/36864K bytes of memory.
Processor board ID FGL1234ABCD
2 Gigabit Ethernet interfaces
"""


class Transport:
    def __init__(self, output: str):
        self.output = output

    async def execute(self, commands: list[str]) -> list[str]:
        assert commands == ["show version"]
        return [self.output]


def facts(state, output: str):
    return asyncio.run(state().get_facts(Transport(output)))


@pytest.mark.parametrize("state", [XeState, ClassicState], ids=["iosxe driver", "ios driver"])
@pytest.mark.parametrize(
    ("output", "os", "version", "model", "serial"),
    [
        (CATALYST_9300, OS.cisco_iosxe, "17.09.04a", "C9300-24P", "FOC2345L0AB"),
        (ISR_4331, OS.cisco_iosxe, "16.09.04", "ISR4331/K9", "FDO21360ABC"),
        (CATALYST_3560CX, OS.cisco_ios, "15.2(7)E13", "WS-C3560CX-12PC-S", "FOC1949Y0AB"),
        (ISR_1941, OS.cisco_ios, "15.7(3)M9", "CISCO1941/K9", "FGL1234ABCD"),
    ],
    ids=["Catalyst 9300", "ISR 4331", "Catalyst 3560CX", "ISR 1941"],
)
def test_the_facts_of_each_platform(state, output, os, version, model, serial):
    found = facts(state, output)

    assert (found.vendor, found.os, found.os_version, found.hardware_model, found.serial_number) == (
        Vendor.cisco,
        os,
        version,
        model,
        serial,
    )
