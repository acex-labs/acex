import asyncio

from acex_devkit.drivers import Transport
from acex_devkit.exceptions import AuthenticationFailed, ConnectionTimeout
from acex_devkit.models.management_connection import ConnectionType
from scrapli.driver.core import AsyncIOSXEDriver
from scrapli.exceptions import ScrapliAuthenticationFailed, ScrapliTimeout


class CiscoIOSTransport(Transport[str]):
    """SSH to Cisco IOS-XE via scrapli. Payloads are CLI text, one command per line."""

    connection_types = {ConnectionType.ssh}

    async def open(self) -> None:
        login = self.credential("userpass")
        enable = self.credential("privilege_escalation", required=False)
        self.conn = AsyncIOSXEDriver(
            host=self.address,
            auth_username=login.fields["username"],
            auth_password=login.fields["password"],
            auth_secondary=(enable or login).fields["password"],
            auth_strict_key=False,
            timeout_ops=120,
            transport="asyncssh",
        )
        try:
            await self.conn.open()
        except ScrapliAuthenticationFailed as e:
            # scrapli reports a timed out SSH handshake as an authentication failure.
            if isinstance(e.__cause__, asyncio.TimeoutError):
                raise ConnectionTimeout(f"Connection to {self.address} timed out") from e
            raise AuthenticationFailed(f"Authentication to {self.address} failed") from e
        except ScrapliTimeout as e:
            raise ConnectionTimeout(f"Connection to {self.address} timed out") from e

    async def close(self) -> None:
        await self.conn.close()

    async def get_config(self) -> str:
        return (await self.conn.send_command("show running-config")).result

    async def apply(self, payload: str) -> str:
        commands = [line.strip() for line in payload.splitlines() if line.strip() not in ("", "!")]
        return (await self.conn.send_configs(commands)).result if commands else ""

    async def execute(self, request: list[str]) -> list[str]:
        return [r.result for r in await self.conn.send_commands(request)]
