from acex_devkit.drivers import NetworkElementDriver
from acex_devkit.models.ned import Platform
from acex_devkit.models.platform import OS, Vendor

from acex_driver_cisco_ioscli.actions import CiscoIOSActions
from acex_driver_cisco_ioscli.codec import CiscoIOSCodec
from acex_driver_cisco_ioscli.state import CiscoIOSState
from acex_driver_cisco_ioscli.transport.transport import CiscoIOSTransport


class CiscoIOSCLIDriver(NetworkElementDriver):
    """Cisco IOS-XE CLI driver."""

    codec_class = CiscoIOSCodec
    transport_class = CiscoIOSTransport
    state_class = CiscoIOSState
    actions_class = CiscoIOSActions

    platforms = [Platform(vendor=Vendor.cisco, os=OS.cisco_iosxe)]
