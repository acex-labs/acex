import asyncio
import re

import asyncssh
from acex_devkit.drivers import Transport
from acex_devkit.exceptions import (
    AuthenticationFailed,
    ConnectionTimeout,
    DriverException,
    HostUnreachable,
    SshAlgorithmMismatch,
)
from acex_devkit.models.management_connection import ConnectionType

# What FortiOS prints when it refuses a line of a configuration it was given.
REJECTED = re.compile(r"parse error|Command fail|Unknown action|Return code -\d+|node_check_object fail", re.IGNORECASE)

# FortiOS pages long output with `--More--` and a command run on its own channel stops after the first page, so the
# pager, a console setting, is turned off for the session and put back before it ends.
PAGER_OFF = ("config system console", "set output standard", "end")
PAGER_ON = ("config system console", "set output more", "end")

# A session prints a prompt before each line it runs and does not echo the line: `FGT-1 # `, `FGT-1 (global) # `. The
# name in it follows the hostname, which a configuration can change in the middle of a session.
PROMPT = re.compile(r"^\S+(?: \([^)]*\))? # ?", re.MULTILINE)


class FortiOSTransport(Transport[str]):
    """SSH to FortiOS over asyncssh. Every command is typed into a CLI session with the pager off, and the output is
    cut out from between the prompts the session prints. Payloads are CLI text, one command per line.

    Checked on a FortiGate-VM 7.6.8 (ARM64 KVM, unlicensed, one VDOM). Not checked: a multi-VDOM unit, where
    `config system console` may need `config global` first and `show full-configuration` from the root VDOM may leave
    the other VDOMs out, and other FortiOS versions."""

    connection_types = {ConnectionType.ssh}

    PORT = 22
    CONNECT_TIMEOUT = 30
    COMMAND_TIMEOUT = 60
    CONFIG_TIMEOUT = 120

    async def open(self) -> None:
        login = self.credential("userpass")
        try:
            self.conn = await asyncssh.connect(
                self.address,
                port=self.PORT,
                username=login.fields["username"],
                password=login.fields["password"],
                known_hosts=None,
                connect_timeout=self.CONNECT_TIMEOUT,
            )
        except asyncssh.PermissionDenied as e:
            raise AuthenticationFailed(f"Authentication to {self.address} failed") from e
        except asyncssh.KeyExchangeFailed as e:
            raise SshAlgorithmMismatch(f"No SSH algorithm in common with the device: {e}") from e
        except TimeoutError as e:
            raise ConnectionTimeout(f"Connection to {self.address} timed out") from e
        except (OSError, asyncssh.Error) as e:
            raise HostUnreachable(f"Could not connect to the device: {e}") from e

    async def close(self) -> None:
        try:
            self.conn.close()
            await self.conn.wait_closed()
        except Exception:
            pass

    async def get_config(self) -> str:
        return await self.run("show full-configuration", self.CONFIG_TIMEOUT)

    async def apply(self, payload: str) -> str:
        script = "\n".join(line.rstrip() for line in payload.splitlines() if line.strip())
        if not script:
            return ""
        output = await self.session(script + "\nexit\n", self.CONFIG_TIMEOUT, "The configuration")
        if REJECTED.search(output):
            raise DriverException(f"The device rejected the configuration:\n{output}")
        return output

    async def execute(self, request: list[str]) -> list[str]:
        return [await self.run(command, self.COMMAND_TIMEOUT) for command in request]

    async def run(self, command: str, timeout: float) -> str:
        """The output of one command, without the prompts around it."""
        script = "\n".join([*PAGER_OFF, command, *PAGER_ON, "exit"]) + "\n"
        return self.output_of(await self.session(script, timeout, command))

    @staticmethod
    def output_of(raw: str) -> str:
        """What the command printed in a session built by `run`: one prompt for each line typed, the command being
        line `len(PAGER_OFF) + 1`, so its output sits after that many prompts and before the prompt that follows it,
        which is the first of the `len(PAGER_ON) + 1` prompts at the end."""
        prompts = list(PROMPT.finditer(raw))
        if len(prompts) < len(PAGER_OFF) + len(PAGER_ON) + 2:
            raise DriverException(f"Could not find the output in what the device printed:\n{raw}")
        start = prompts[len(PAGER_OFF)].end()
        stop = prompts[-(len(PAGER_ON) + 1)].start()
        return raw[start:stop].rstrip("\n") + "\n"

    async def session(self, script: str, timeout: float, what: str) -> str:
        """Everything the CLI printed while `script` was typed into a session."""
        try:
            result = await asyncio.wait_for(self.conn.run(None, input=script, check=False), timeout)
        except TimeoutError as e:
            raise ConnectionTimeout(f"{what} did not finish within {timeout:.0f} s") from e
        return str(result.stdout or "")
