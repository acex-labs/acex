"""OS version schemes.

One declaration per OS, saying which version strings that platform may report.
Add an OS by adding a class; add a spelling by adding a pattern. Nothing here
needs touching when a vendor ships a new release - that is the point.

Group names ``major``, ``minor``, ``patch``, ``build`` and ``qualifier`` are
what make a version comparable; a pattern may name only the ones it has.
"""

from acex_devkit.models.os_version import OsVersionScheme
from acex_devkit.models.platform import OS

# 17.9.4a, 16.12.5b, 10.2.5 - dotted, with an optional rebuild letter
DOTTED = r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?P<qualifier>[A-Za-z]\w*)?"
# 15.2(7)E3, 12.2(55)SE12, 9.3(8) - Cisco train notation
TRAIN = r"(?P<major>\d+)\.(?P<minor>\d+)\((?P<patch>\d+)\)(?P<qualifier>[A-Za-z]\w*)?"
# 4.30.3M, 4.28.6.1M - dotted with an optional fourth component, as Arista EOS uses
DOTTED_BUILD = (
    r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:\.(?P<build>\d+))?"
    r"(?P<qualifier>[A-Za-z]\w*)?"
)
# 22.4R1.10, 20.4R3-S4, 22.4R1-S2.3 - Junos release, optional spin and service release
JUNOS = (
    r"(?P<major>\d+)\.(?P<minor>\d+)R(?P<patch>\d+)"
    r"(?:-(?P<qualifier>S\d+))?"
    r"(?:\.(?P<build>\d+))?"
)


class CiscoIosVersions(OsVersionScheme):
    os: OS = OS.cisco_ios
    patterns: list[str] = [TRAIN, DOTTED]
    examples: list[str] = ["15.2(7)E3", "12.2(55)SE12", "15.0(2)SE11"]


class CiscoIosXeVersions(OsVersionScheme):
    os: OS = OS.cisco_iosxe
    patterns: list[str] = [DOTTED, TRAIN]
    examples: list[str] = ["17.9.4a", "17.12.3a", "16.12.5b"]


class CiscoIosXrVersions(OsVersionScheme):
    os: OS = OS.cisco_iosxr
    patterns: list[str] = [DOTTED]
    examples: list[str] = ["7.5.2", "7.11.1"]


class CiscoNxosVersions(OsVersionScheme):
    os: OS = OS.cisco_nxos
    patterns: list[str] = [DOTTED, TRAIN]
    examples: list[str] = ["10.2.5", "9.3(8)"]


class JuniperJunosVersions(OsVersionScheme):
    os: OS = OS.juniper_junos
    patterns: list[str] = [JUNOS]
    examples: list[str] = ["22.4R1.10", "20.4R3-S4", "22.4R1-S2.3", "21.2R3"]


class FortinetFortiosVersions(OsVersionScheme):
    os: OS = OS.fortinet_fortios
    patterns: list[str] = [DOTTED]
    examples: list[str] = ["7.2.5", "7.4.1"]


class AristaEosVersions(OsVersionScheme):
    os: OS = OS.arista_eos
    patterns: list[str] = [DOTTED_BUILD]
    examples: list[str] = ["4.30.3M", "4.28.6.1M"]
