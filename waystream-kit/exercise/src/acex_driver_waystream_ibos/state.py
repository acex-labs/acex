from dataclasses import dataclass

from acex_devkit.drivers import State

from acex_driver_waystream_ibos.transport import IbosTransport


@dataclass(frozen=True)
class IbosFacts:
    hostname: str | None = None
    os_version: str | None = None  # 6.3.0-ED-R
    image: str | None = None  # ibos-ms4k-6.3.0-ED-R
    hardware_model: str | None = None  # MS4026-AC
    serial_number: str | None = None  # 0008AE00D004


def parse_show_version(output: str) -> IbosFacts:
    raise NotImplementedError("Exercise 7: read the facts out of show version")


async def read_facts(transport: IbosTransport) -> IbosFacts:
    raise NotImplementedError("Exercise 7: run show version through the transport and parse it")


class IbosState(State):
    # Exercise 7: get_facts returns DeviceFacts, which needs the Waystream vendor and OS of the devkit (acex PR 386).
    pass
