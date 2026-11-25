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

# FortiOS pages long output with `--More--` and waits for a key. The marker, with or without a space after it, is
# the last thing printed while it waits.
# When the key arrives, the device echoes it and erases the marker (a carriage return, spaces, a carriage return), and
# prints the next page.
MORE = "--More--"
MORE_ERASED = re.compile(r"--More--[ ]*\r[ ]+\r")

# The pager is answered, not switched off: `config system console` is a write, which a read-only administrator
# profile may not have, and on a unit with VDOMs it does nothing at the top level (the pager then stays on and the
# output is cut at the first page). A page takes a key, and the keys are sent in batches so that a long configuration
# does not cost a round trip for each page. Keys left over when the output ends are typed at the prompt and do no harm.
PAGE_KEYS = b" " * 32

# A prompt is `FGT-1 # ` or `FGT-1 (global) # `: the name follows the hostname, which a configuration can change.
PROMPT_LINE = re.compile(r"^\S+(?: \([^)]*\))? # ?$")

# How long nothing may arrive after what looks like a prompt for it to be the prompt: a line of a configuration can
# look like one.
QUIET = 0.25

# How long the pager may stay at its marker, with keys sent, before more keys are sent.
STUCK = 2.0

# What a complete `show full-configuration` looks like from the top level: it begins with a header comment, ends with
# the closing line of the last block, and on a unit with VDOMs holds the global part (`config global`) and every VDOM.
CONFIG_HEADER = "#config-version="
VDOMS_ON = re.compile(r":vdom=1(?::|$)")


class FortiOSTransport(Transport[str]):
    """SSH to FortiOS over asyncssh. A command is typed into a CLI session of its own, the pager is answered with a
    key for every page, and the output is cut out from before the prompt the session prints when it is done. Payloads
    are CLI text, one command per line. Nothing in the device is changed to read it.

    A read that is not complete is an error: the pager still holding the output, a session that ended early, a
    configuration without its header or its last line, or a unit with VDOMs read without its global part (an
    administrator limited to one VDOM sees only that VDOM).

    Checked on a FortiGate-VM 7.6.8 (ARM64 KVM, unlicensed), with one VDOM and with VDOMs enabled, as the global
    administrator. Not checked: an administrator limited to one VDOM, an administrator profile with read access only,
    and other FortiOS versions."""

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
        return self.complete_configuration(await self.run("show full-configuration", self.CONFIG_TIMEOUT))

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
        """The output of one command, with the pager answered and without the prompt after it."""
        try:
            text = await asyncio.wait_for(self.read(command), timeout)
        except TimeoutError as e:
            raise ConnectionTimeout(f"{command} did not finish within {timeout:.0f} s") from e
        text = MORE_ERASED.sub("", text).replace("\r", "")
        if MORE in text:
            raise DriverException(f"The output of {command} was cut off by the pager:\n{text[-500:]}")
        lines = text.split("\n")
        if not PROMPT_LINE.match(lines[-1]):
            raise DriverException(f"The session did not end at a prompt after {command}:\n{text[-500:]}")
        return "\n".join(lines[:-1]).rstrip("\n") + "\n"

    async def read(self, command: str) -> str:
        """What the session prints for `command`, up to and including the prompt that follows, with the markers of
        the pager still in it."""
        process = await self.conn.create_process(encoding=None)
        try:
            await self.collect(process, answering=False)
            process.stdin.write(command.encode() + b"\n")
            text = await self.collect(process, answering=True)
            process.stdin.write(b"exit\n")
            return text
        finally:
            process.close()

    @staticmethod
    async def collect(process, answering: bool) -> str:
        """Everything printed until a prompt that nothing follows. With `answering`, every page is given a key."""
        text, sent, consumed = "", 0, 0
        while True:
            at_prompt = PROMPT_LINE.match(text[text.rfind("\n") + 1 :]) is not None
            waiting = answering and text.rstrip(" ").endswith(MORE)
            try:
                chunk = await asyncio.wait_for(
                    process.stdout.read(65536), QUIET if at_prompt else STUCK if waiting else None
                )
            except TimeoutError:
                if waiting:
                    # Still at the marker: the keys were not taken, so more are sent.
                    process.stdin.write(PAGE_KEYS)
                    sent += len(PAGE_KEYS)
                    continue
                return text
            if not chunk:
                raise DriverException(f"The device ended the session before the output was complete:\n{text[-500:]}")
            new = chunk.decode("utf-8", errors="replace")
            tail = text[-32:]
            text += new
            if answering:
                # The keys the device has taken are the markers it has erased.
                consumed += sum(1 for m in MORE_ERASED.finditer(tail + new) if m.end() > len(tail))
                if text.rstrip(" ").endswith(MORE) and sent - consumed <= 0:
                    process.stdin.write(PAGE_KEYS)
                    sent += len(PAGE_KEYS)

    async def session(self, script: str, timeout: float, what: str) -> str:
        """Everything the CLI printed while `script` was typed into a session."""
        try:
            result = await asyncio.wait_for(self.conn.run(None, input=script, check=False), timeout)
        except TimeoutError as e:
            raise ConnectionTimeout(f"{what} did not finish within {timeout:.0f} s") from e
        return str(result.stdout or "")

    @staticmethod
    def complete_configuration(text: str) -> str:
        """`text` if it is a whole configuration, else a DriverException that says what is missing."""
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines or not lines[0].startswith(CONFIG_HEADER):
            raise DriverException(f"The configuration does not begin with its header ({CONFIG_HEADER}):\n{text[:300]}")
        if lines[-1] != "end":
            raise DriverException(f"The configuration does not end where a configuration ends:\n{text[-300:]}")
        if VDOMS_ON.search(lines[0]) and "config global" not in lines:
            raise DriverException(
                "The unit has VDOMs but the configuration read has no global part: the account sees one VDOM only. "
                "Use an administrator that can see all VDOMs, the global part and every VDOM."
            )
        return text
