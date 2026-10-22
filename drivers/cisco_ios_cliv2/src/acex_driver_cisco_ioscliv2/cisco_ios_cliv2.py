from acex_devkit.drivers import NetworkElementDriver
from acex_devkit.models.ned import Platform
from acex_devkit.models.platform import OS, Vendor

from acex_driver_cisco_ioscliv2.codec import CiscoIOSCodec
from acex_driver_cisco_ioscliv2.transport.transport import CiscoIOSTransport


class CiscoIOSCLIDriverV2(NetworkElementDriver):
    """Cisco IOS-XE CLI driver."""

    codec_class = CiscoIOSCodec
    transport_class = CiscoIOSTransport

    platforms = [Platform(vendor=Vendor.cisco, os=OS.cisco_iosxe)]
