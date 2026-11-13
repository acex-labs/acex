import asyncio
import contextlib
import ipaddress
import logging

import asyncssh

from ibos_kit.masking import mask
from ibos_kit.mock.engine import Session
from ibos_kit.mock.scenarios import CREDENTIALS, Device, device_for

log = logging.getLogger("ibos_kit.mock")
LEGACY_KEX = ["diffie-hellman-group14-sha1"]


def ensure_loopback(host: str) -> str:
    address = "127.0.0.1" if host == "localhost" else host
    try:
        ok = ipaddress.ip_address(address).is_loopback
    except ValueError:
        ok = False
    if not ok:
        raise ValueError(f"the mock only listens on a loopback address, not {host!r}")
    return address


class _Server(asyncssh.SSHServer):
    def __init__(self, mock: "RunningMock", reject_logins: bool):
        self.mock = mock
        self.reject_logins = reject_logins
        self.connection = None

    def connection_made(self, conn):
        self.connection = conn
        self.mock.connections.add(conn)

    def connection_lost(self, exc):
        self.mock.connections.discard(self.connection)

    def begin_auth(self, username):
        return True

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        return not self.reject_logins and (username, password) == (CREDENTIALS["username"], CREDENTIALS["password"])


class RunningMock:
    def __init__(self, device: Device, host: str = "127.0.0.1", port: int = 0):
        self.device = device
        self.host = ensure_loopback(host)
        self.port = port
        self.sessions: list[Session] = []
        self.connections: set = set()
        self._server: asyncssh.SSHAcceptor | None = None

    async def __aenter__(self) -> "RunningMock":
        faults = self.device.faults
        self._server = await asyncssh.create_server(
            lambda: _Server(self, faults.reject_logins),
            host=self.host,
            port=self.port,
            server_host_keys=[asyncssh.generate_private_key("ssh-ed25519")],
            process_factory=self._process,
            kex_algs=LEGACY_KEX if faults.legacy_kex_only else (),
        )
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc) -> None:
        for connection in list(self.connections):
            connection.abort()
        self._server.close()
        await asyncio.wait_for(self._server.wait_closed(), 5)

    async def _process(self, process: asyncssh.SSHServerProcess) -> None:
        session = Session(self.device)
        self.sessions.append(session)
        latency = self.device.faults.latency_ms / 1000
        process.stdout.write(session.greeting())
        buffer, hidden = "", False
        async for chunk in process.stdin:
            buffer += chunk
            while "\n" in buffer or "\r" in buffer:
                line, _, buffer = buffer.replace("\r\n", "\n").replace("\r", "\n").partition("\n")
                before = len(session.trace)
                reply = session.handle(line)
                for entry in session.trace[before:]:
                    flag = "assumed" if entry.assumed else entry.level.lower()
                    log.info("[%s] %s %s", flag, mask(entry.command).text.strip(), ",".join(entry.facts))
                if latency:
                    await asyncio.sleep(latency)
                if reply.hang:
                    await asyncio.sleep(3600)
                out = ("\n" if hidden else "") + reply.text
                if reply.prompt_follows:
                    out += ("\n" if reply.text else "") + session.prompt
                process.stdout.write(out)
                await process.stdout.drain()
                if reply.drop:
                    process.channel.get_connection().abort()
                    return
                if reply.close:
                    process.exit(0)
                    return
                hidden = not reply.echo
                with contextlib.suppress(AssertionError):  # a client without a terminal type gets no line editor
                    process.channel.set_echo(reply.echo)
        process.exit(0)


def build(scenario: str, **overrides) -> RunningMock:
    host = overrides.pop("host", "127.0.0.1")
    port = overrides.pop("port", 0)
    return RunningMock(device_for(scenario, **overrides), host=host, port=port)
