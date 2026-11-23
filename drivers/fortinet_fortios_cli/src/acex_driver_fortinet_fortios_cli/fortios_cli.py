from acex_devkit.drivers import NetworkElementDriver
from acex_devkit.models.ned import Platform
from acex_devkit.models.platform import OS, Vendor

from acex_driver_fortinet_fortios_cli.codec import FortiOSCodec
from acex_driver_fortinet_fortios_cli.state import FortiOSState
from acex_driver_fortinet_fortios_cli.transport.transport import FortiOSTransport


class FortiOSCLIDriver(NetworkElementDriver):
    """Fortinet FortiOS CLI driver."""

    codec_class = FortiOSCodec
    transport_class = FortiOSTransport
    state_class = FortiOSState

    platforms = [Platform(vendor=Vendor.fortinet, os=OS.fortinet_fortios)]

    interface_version = 2
