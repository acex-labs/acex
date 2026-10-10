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
CONFIG_FILE = CONFIG_DIR / f"{HOSTNAME}.txt"
FALLBACK_CONFIG = CONFIG_DIR / "default.txt"

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
    elif cmd == "show running-config":
        return _load_config().rstrip("\n") + PROMPT
    elif "lldp neighbors" in cmd:
        return LLDP_EMPTY + PROMPT
    elif "cdp neighbors" in cmd:
        return CDP_EMPTY + PROMPT
    else:
        return PROMPT


async def handle_client(process: asyncssh.SSHServerProcess):
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
            response = _handle(line)
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
    key_path = pathlib.Path("/etc/ssh/mock_host_key")
    if not key_path.exists():
        key = asyncssh.generate_private_key("ssh-rsa")
        key.write_private_key(str(key_path))

    server_key = asyncssh.read_private_key(str(key_path))

    await asyncssh.create_server(
        MockSSHServer,
        host="",
        port=SSH_PORT,
        server_host_keys=[server_key],
        process_factory=handle_client,
    )
    log.info(f"Mock IOS XE device '{HOSTNAME}' listening on port {SSH_PORT}")
    await asyncio.get_event_loop().create_future()


asyncio.run(main())
