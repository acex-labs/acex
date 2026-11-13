from acex_devkit.drivers import NetworkElementDriver
from acex_devkit.models.ned import Platform
from acex_devkit.models.platform import OS, Vendor

from acex_driver_cisco_ios_classic_cli.actions import CiscoIOSActions
from acex_driver_cisco_ios_classic_cli.codec import CiscoIOSCodec
from acex_driver_cisco_ios_classic_cli.state import CiscoIOSState
from acex_driver_cisco_ios_classic_cli.transport.transport import CiscoIOSTransport


class CiscoIOSClassicCLIDriver(NetworkElementDriver):
    """Cisco IOS CLI driver."""

    codec_class = CiscoIOSCodec
    transport_class = CiscoIOSTransport
    state_class = CiscoIOSState
    actions_class = CiscoIOSActions

    platforms = [Platform(vendor=Vendor.cisco, os=OS.cisco_ios)]
