from acex_devkit.drivers import Transport
from acex_devkit.models.management_connection import ConnectionType


class IbosTransport(Transport[str]):
    connection_types = {ConnectionType.ssh}

    PORT = 22
    timeout_socket = 10
    timeout_ops = 30

    # Exercise 8 reads this. Configuration mode is not verified for iBOS, so writing stays off by default.
    allow_unverified_config_mode = False

    async def open(self) -> None:
        raise NotImplementedError("Exercise 2: open the SSH session")

    async def close(self) -> None:
        raise NotImplementedError("Exercise 2: close the SSH session")

    async def execute(self, request: list[str]) -> list[str]:
        raise NotImplementedError("Exercise 2: run commands, one output per command")

    async def get_config(self) -> str:
        raise NotImplementedError("Exercise 3: the raw running configuration")

    async def apply(self, payload: str) -> str:
        raise NotImplementedError("Exercise 8: send configuration (experimental)")
