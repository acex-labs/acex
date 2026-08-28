"""Mock IOS XE SSH server — responds to Scrapli's command set with static configs."""

import asyncio
import logging
import os
import pathlib

import asyncssh

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("mock-device")

HOSTNAME = os.environ.get("MOCK_HOSTNAME", "mock-router")
SSH_PORT = int(os.environ.get("SSH_PORT", "22"))
USERNAME = os.environ.get("SSH_USERNAME", "admin")
PASSWORD = os.environ.get("SSH_PASSWORD", "admin")

CONFIG_DIR = pathlib.Path("/configs")
CONFIG_FILE = CONFIG_DIR / f"{HOSTNAME}.txt"
FALLBACK_CONFIG = CONFIG_DIR / "default.txt"


def _load_config() -> str:
    for path in (CONFIG_FILE, FALLBACK_CONFIG):
        if path.exists():
            return path.read_text()
    return f"hostname {HOSTNAME}\n!\nend\n"


LLDP_EMPTY = "% LLDP is not enabled"
CDP_EMPTY = "% CDP is not enabled"
PROMPT = f"\n{HOSTNAME}#"


def _handle(cmd: str) -> str:
    cmd = cmd.strip()
    log.info(f"CMD: {cmd!r}")
    if not cmd or cmd.startswith("terminal"):
        return PROMPT
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
