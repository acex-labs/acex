import asyncio

from acex_devkit.drivers import Transport
from acex_devkit.exceptions import AuthenticationFailed, ConnectionTimeout
from acex_devkit.models.management_connection import ConnectionType
from scrapli.driver.core import AsyncIOSXEDriver
from scrapli.exceptions import ScrapliAuthenticationFailed, ScrapliTimeout


class CiscoIOSTransport(Transport[str]):
    """SSH to Cisco IOS / IOS-XE via scrapli. Payloads are CLI text, one command per line."""

    connection_types = {ConnectionType.ssh}

    PORT = 22

    # Legacy KEX/ciphers for older IOS devices that don't support modern algorithms
    LEGACY_ASYNCSSH_OPTIONS = {
        "kex_algs": [
            "diffie-hellman-group-exchange-sha256",
            "diffie-hellman-group-exchange-sha1",
            "diffie-hellman-group14-sha256",
            "diffie-hellman-group14-sha1",
            "diffie-hellman-group1-sha1",
        ],
    }

    async def open(self) -> None:
        login = self.credential("userpass")
        enable = self.credential("privilege_escalation", required=False)
        self.conn = AsyncIOSXEDriver(
            host=self.address,
            auth_username=login.fields["username"],
            auth_password=login.fields["password"],
            auth_secondary=enable.fields["password"] if enable else login.fields["password"],
            auth_strict_key=False,
            port=self.PORT,
            timeout_socket=30,
            timeout_ops=120,
            transport="asyncssh",
            transport_options={"asyncssh": self.LEGACY_ASYNCSSH_OPTIONS},
        )
        try:
            await self.conn.open()
        except ScrapliAuthenticationFailed as e:
            if isinstance(e.__cause__, asyncio.TimeoutError):
                raise ConnectionTimeout(f"Connection to {self.address} timed out") from e
            raise AuthenticationFailed(f"Authentication to {self.address} failed") from e
        except ScrapliTimeout as e:
            raise ConnectionTimeout(f"Connection to {self.address} timed out") from e

    async def close(self) -> None:
        try:
            await self.conn.close()
        except Exception:
            pass

    async def get_config(self) -> str:
        return (await self.conn.send_command("show running-config", timeout_ops=120)).result

    async def apply(self, payload: str) -> str:
        commands = [line.strip() for line in payload.splitlines() if line.strip() and line.strip() != "!"]
        if not commands:
            return ""
        return (await self.conn.send_configs(commands)).result

    async def execute(self, request: list[str]) -> list[str]:
        return [r.result for r in await self.conn.send_commands(request, timeout_ops=120)]

    async def send(self, command: str, timeout: float) -> str:
        """One command that may take longer than the usual operation timeout, e.g. a long ping."""
        return (await self.conn.send_command(command, timeout_ops=timeout)).result
