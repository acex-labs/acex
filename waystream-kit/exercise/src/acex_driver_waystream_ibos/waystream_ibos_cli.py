from acex_devkit.drivers import NetworkElementDriver

from acex_driver_waystream_ibos.codec import IbosCodec
from acex_driver_waystream_ibos.state import IbosState
from acex_driver_waystream_ibos.transport import IbosTransport


class WaystreamIbosDriver(NetworkElementDriver):
    codec_class = IbosCodec
    transport_class = IbosTransport
    state_class = IbosState

    # The devkit has no Vendor or OS for Waystream yet; platforms are declared when it does.
    platforms = []
