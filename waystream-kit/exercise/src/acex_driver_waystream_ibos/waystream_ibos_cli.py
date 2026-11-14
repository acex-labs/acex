from acex_devkit.drivers import NetworkElementDriver

from acex_driver_waystream_ibos.codec import IbosCodec
from acex_driver_waystream_ibos.state import IbosState
from acex_driver_waystream_ibos.transport import IbosTransport


class WaystreamIbosDriver(NetworkElementDriver):
    codec_class = IbosCodec
    transport_class = IbosTransport
    state_class = IbosState

    # Exercise 7: declare the platform. The devkit has had Waystream since acex pull request 386.
    platforms = []
