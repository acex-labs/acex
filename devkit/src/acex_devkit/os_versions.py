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
# 7.0(3)I7(9), 9.3(8), 7.0(3)I7 - NX-OS train notation. The qualifier is the train (I7) and the number in the last
# parentheses is the rebuild of that train, which is the build component: 7.0(3)I7 sorts before 7.0(3)I7(9), and
# (10) after (9). A rebuild follows a train, so 9.3(8)(2) is not a version.
TRAIN_REBUILD = (
    r"(?P<major>\d+)\.(?P<minor>\d+)\((?P<patch>\d+)\)"
    r"(?:(?P<qualifier>[A-Za-z]\w*)(?:\((?P<build>\d+)\))?)?"
)
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
# 6.3.5-ED-R, 7.6.2-GD-R, 6.1.0-ED-RC2 - Waystream iBOS. The letters after the first dash are the release class
# (ED, GD); what follows them (R, RC2) is accepted but not compared.
IBOS = (
    r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<qualifier>[A-Za-z]+)(?:-[A-Za-z0-9]+)*)?"
)
# 6.49.17, 7.16.1, 7.17 - MikroTik RouterOS. A release can be two numbers (7.17) and the testing channel adds beta and
# rc (7.17beta2, 7.17rc3). The channel that `/system resource print` writes after the number, such as (stable), is not
# part of the version. A pre-release sorts after its release here, since the qualifier compares as text; nothing
# decides on order, it only orders a list.
ROUTEROS = (
    r"(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?"
    r"(?P<qualifier>(?:beta|rc)\d+)?"
)


class CiscoBusinessVersions(OsVersionScheme):
    """Cisco Business firmware (Catalyst 1300, CBS250 and CBS350). It numbers its releases with four components, which
    the IOS and IOS-XE schemes take as three and reject."""

    os: OS = OS.cisco_business
    patterns: list[str] = [DOTTED_BUILD]
    examples: list[str] = ["4.1.7.17", "4.1.7.24", "4.1.6.54", "4.1.3.36"]


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
    patterns: list[str] = [DOTTED, TRAIN_REBUILD]
    examples: list[str] = ["10.2.5", "9.3(8)", "7.0(3)I7(9)"]


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


class MikrotikRouterosVersions(OsVersionScheme):
    os: OS = OS.mikrotik_routeros
    patterns: list[str] = [ROUTEROS]
    examples: list[str] = ["7.17", "7.16.1", "6.49.17", "7.17rc3"]


class WaystreamIbosVersions(OsVersionScheme):
    os: OS = OS.waystream_ibos
    patterns: list[str] = [IBOS]
    examples: list[str] = ["6.3.5-ED-R", "7.6.2-GD-R", "6.1.0-ED-RC2"]
