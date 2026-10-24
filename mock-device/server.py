"""Mock IOS XE SSH server — responds to Scrapli's command set with static configs."""

import asyncio
import hashlib
import logging
import os
import pathlib
import time

import asyncssh

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("mock-device")

HOSTNAME = os.environ.get("MOCK_HOSTNAME", "mock-router")
# The address to listen on, e.g. a loopback alias like 127.0.0.2 to run several devices on one host.
BIND = os.environ.get("MOCK_BIND", "")
SSH_PORT = int(os.environ.get("SSH_PORT", "22"))
USERNAME = os.environ.get("SSH_USERNAME", "admin")
PASSWORD = os.environ.get("SSH_PASSWORD", "admin")

# Derived from hostname so every mock container gets a stable, unique identity
_HOST_HASH = hashlib.sha256(HOSTNAME.encode()).hexdigest().upper()

OS_NAME = os.environ.get("MOCK_OS", "IOS XE")
OS_VERSION = os.environ.get("MOCK_OS_VERSION", "17.09.04a")
MODEL = os.environ.get("MOCK_MODEL", "C9300-48P")
SERIAL = os.environ.get("MOCK_SERIAL", f"FOC{int(_HOST_HASH[:8], 16) % 10000:04d}{_HOST_HASH[8:12]}")
BASE_MAC = "70:18:a7:" + ":".join(_HOST_HASH[i : i + 2].lower() for i in (12, 14)) + ":00"
START_TIME = time.monotonic()

CONFIG_DIR = pathlib.Path("/configs")
# The running-config to serve; by default the hostname's file in /configs, else default.txt there.
CONFIG_FILE = pathlib.Path(os.environ.get("MOCK_CONFIG", CONFIG_DIR / f"{HOSTNAME}.txt"))
FALLBACK_CONFIG = CONFIG_DIR / "default.txt"
# Each device on a host needs its own key file, somewhere it may write.
HOST_KEY = pathlib.Path(os.environ.get("MOCK_HOST_KEY", "/etc/ssh/mock_host_key"))
# Ping targets that never answer, comma separated; every other target answers every packet.
UNREACHABLE = {t.strip() for t in os.environ.get("MOCK_UNREACHABLE", "").split(",") if t.strip()}

SHOW_VERSION_TEMPLATE = (pathlib.Path(__file__).parent / "show_version.txt").read_text()


def _load_config() -> str:
    for path in (CONFIG_FILE, FALLBACK_CONFIG):
        if path.exists():
            return path.read_text()
    return f"hostname {HOSTNAME}\n!\nend\n"


LLDP_EMPTY = "% LLDP is not enabled"
CDP_EMPTY = "% CDP is not enabled"
PROMPT = f"\n{HOSTNAME}#"


def _short_version(version: str) -> str:
    """17.09.04a -> 17.9.4a, as printed on the IOS Software line."""
    return ".".join(part.lstrip("0") or "0" for part in version.split("."))


def _uptime() -> str:
    remaining = int(time.monotonic() - START_TIME) // 60
    parts = []
    for unit, size in (("week", 7 * 24 * 60), ("day", 24 * 60), ("hour", 60), ("minute", 1)):
        value, remaining = divmod(remaining, size)
        if value:
            parts.append(f"{value} {unit}{'s' if value != 1 else ''}")
    return ", ".join(parts) or "0 minutes"


def _show_version() -> str:
    uptime = _uptime()
    return SHOW_VERSION_TEMPLATE.format(
        OS_NAME=OS_NAME,
        OS_VERSION=OS_VERSION,
        SHORT_VERSION=_short_version(OS_VERSION),
        HOSTNAME=HOSTNAME,
        UPTIME=uptime,
        MODEL=MODEL,
        SERIAL=SERIAL,
        BASE_MAC=BASE_MAC,
    )


def _ping(cmd: str) -> str:
    """`ping [vrf X] target [repeat N] [size S] [df-bit] [timeout T] ...` answered as IOS does."""
    words = cmd.split()[1:]
    if words[:1] == ["vrf"]:
        words = words[2:]
    if not words:
        return "% Incomplete command."
    target, options = words[0], dict(zip(words[1::2], words[2::2], strict=False))
    count, size, timeout = int(options.get("repeat", 5)), options.get("size", "100"), options.get("timeout", "2")
    answers = 0 if target in UNREACHABLE else count
    summary = f"Success rate is {answers * 100 // count} percent ({answers}/{count})"
    if answers:
        summary += ", round-trip min/avg/max = 1/2/4 ms"
    return (
        "Type escape sequence to abort.\n"
        f"Sending {count}, {size}-byte ICMP Echos to {target}, timeout is {timeout} seconds:\n"
        + "!" * answers
        + "." * (count - answers)
        + "\n"
        + summary
    )


def _is_show_version(cmd: str) -> bool:
    words = cmd.split()
    return (
        len(words) == 2
        and len(words[0]) >= 2
        and "show".startswith(words[0])
        and len(words[1]) >= 3
        and "version".startswith(words[1])
    )


def _handle(cmd: str) -> str:
    cmd = cmd.strip()
    log.info(f"CMD: {cmd!r}")
    if not cmd or cmd.startswith("terminal"):
        return PROMPT
    elif _is_show_version(cmd):
        return _show_version().rstrip("\n") + PROMPT
    elif cmd.split()[0] == "ping":
        return _ping(cmd) + PROMPT
    elif "lldp neighbors" in cmd:
        return LLDP_EMPTY + PROMPT
    elif "cdp neighbors" in cmd:
        return CDP_EMPTY + PROMPT
    else:
        return PROMPT


class CliSession:
    """One SSH session's CLI mode: exec, global configuration, or a configuration submode.

    What is entered in configuration mode is kept for the device's lifetime and
    shows in `show running-config`, so a push can be checked afterwards.
    """

    #: Lines entered in configuration mode since the device started, shared by all sessions.
    pushed: list[str] = []

    #: Commands that enter a configuration submode, by their first word, and the submode's prompt.
    SUBMODES = {"interface": "config-if", "line": "config-line", "router": "config-router", "vlan": "config-vlan"}

    def __init__(self):
        #: None in exec mode, otherwise the mode shown in the prompt, e.g. "config" or "config-if".
        self.mode: str | None = None

    @property
    def prompt(self) -> str:
        return f"\n{HOSTNAME}({self.mode})#" if self.mode else PROMPT

    def handle(self, cmd: str) -> str:
        line = cmd.strip()
        if self.mode is None:
            return self._exec(line, cmd)
        return self._configure(line)

    def _exec(self, line: str, cmd: str) -> str:
        words = line.split()
        if len(words) >= 1 and words[0].startswith("conf") and "configure".startswith(words[0]):
            log.info(f"CMD: {line!r}")
            self.mode = "config"
            return "Enter configuration commands, one per line.  End with CNTL/Z." + self.prompt
        if line in ("write memory", "wr", "copy running-config startup-config"):
            log.info(f"CMD: {line!r}")
            return "Building configuration...\n[OK]" + self.prompt
        if line == "show running-config":
            log.info(f"CMD: {line!r}")
            return self.running_config().rstrip("\n") + self.prompt
        return _handle(cmd)

    def _configure(self, line: str) -> str:
        if not line:
            return self.prompt
        if line == "end":
            self.mode = None
            return self.prompt
        if line == "exit":
            self.mode = None if self.mode == "config" else "config"
            return self.prompt
        log.info(f"CONFIG ({self.mode}): {line!r}")
        submode = self.SUBMODES.get(line.split()[0])
        if submode is not None:
            self.mode = submode
            self.pushed.append(line)
        else:
            # Lines arrive without their indentation; indent those entered in a submode.
            self.pushed.append(f" {line}" if self.mode != "config" else line)
        return self.prompt

    @classmethod
    def running_config(cls) -> str:
        """The configuration file, with what has been entered since appended."""
        base = _load_config().rstrip()
        if not cls.pushed:
            return base + "\n"
        if base.endswith("end"):
            base = base[: -len("end")].rstrip()
        return "\n".join([base, "!", *cls.pushed, "!", "end"]) + "\n"


async def handle_client(process: asyncssh.SSHServerProcess):
    session = CliSession()
    process.stdout.write(PROMPT)
    await process.stdout.drain()

    buf = ""
    async for chunk in process.stdin:
        buf += chunk
        while "\n" in buf or "\r" in buf:
            for sep in ("\r\n", "\n", "\r"):
                if sep in buf:
                    line, buf = buf.split(sep, 1)
                    break
            response = session.handle(line)
            process.stdout.write(response)
            await process.stdout.drain()

    process.exit(0)


class MockSSHServer(asyncssh.SSHServer):
    def begin_auth(self, username):
        return True

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        return username == USERNAME and password == PASSWORD


async def main():
    key_path = HOST_KEY
    if not key_path.exists():
        key = asyncssh.generate_private_key("ssh-rsa")
        key.write_private_key(str(key_path))

    server_key = asyncssh.read_private_key(str(key_path))

    await asyncssh.create_server(
        MockSSHServer,
        host=BIND,
        port=SSH_PORT,
        server_host_keys=[server_key],
        process_factory=handle_client,
    )
    log.info(f"Mock IOS XE device '{HOSTNAME}' listening on {BIND or '*'}:{SSH_PORT}, serving {CONFIG_FILE}")
    await asyncio.get_event_loop().create_future()


asyncio.run(main())
