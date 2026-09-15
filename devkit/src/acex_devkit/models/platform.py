"""Platform identity.

Vendor and OS are the two closed sets an integrator picks from when declaring
an asset. They live apart from the asset model so that everything describing a
platform - device types, version schemes - can name them without importing the
asset itself.
"""

from enum import StrEnum


class OS(StrEnum):
    arista_eos = "arista_eos"
    cisco_ios = "cisco_ios"
    cisco_iosxe = "cisco_iosxe"
    cisco_iosxr = "cisco_iosxr"
    cisco_nxos = "cisco_nxos"
    fortinet_fortios = "fortinet_fortios"
    juniper_junos = "juniper_junos"


class Vendor(StrEnum):
    arista = "arista"
    cisco = "cisco"
    fortinet = "fortinet"
    juniper = "juniper"
