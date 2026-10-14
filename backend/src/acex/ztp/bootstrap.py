"""ZTP bootstraps: what each ZTP method serves a device from acex, and the DHCP options that point the device to it.

Every `ZtpMethod` has one. The bootstrap endpoint serves it and the DHCP config is rendered from it,
so a method can't be added without both.
"""

from acex.constants import BASE_URL
from acex_devkit.models.ztp import ZtpMethod


class ZtpBootstrap:
    method: ZtpMethod
    #: The file the device fetches.
    filename: str
    media_type: str = "text/plain"

    @property
    def path(self) -> str:
        """Where acex serves the bootstrap."""
        return f"{BASE_URL}/ztp/init_config/{self.method}/{self.filename}"

    def url(self, base_url: str) -> str:
        """The bootstrap's URL on the acex at `base_url`."""
        return f"{base_url.rstrip('/')}{self.path}"

    def render(self, username: str, password: str) -> str:
        """The init config a device gets, with the temporary login discovery uses."""
        raise NotImplementedError

    def dhcp_options(self, url: str) -> list[dict]:
        """Kea `option-data` that points a device bootstrapping this way to `url`."""
        raise NotImplementedError


class CiscoIosxePythonBootstrap(ZtpBootstrap):
    """IOS XE downloads the script from the URL in option 67 and runs it in guestshell."""

    method = ZtpMethod.cisco_iosxe_python
    filename = "ztp.py"
    media_type = "application/x-python"

    def render(self, username: str, password: str) -> str:
        commands = [
            "hostname acex-ztp-init-device",
            "ip domain name example.com",
            # The temporary login discovery uses, until onboarding rotates it.
            f"username {username} privilege 15 secret 0 {password}",
            "crypto key generate rsa modulus 2048",
            "ip ssh version 2",
            "line vty 0 15",
            "transport input ssh",
            "login local",
            "end",
        ]
        # repr() quotes each command, so a login cannot break out of the script.
        lines = "".join(f"        {command!r},\n" for command in commands)
        return f"""#!/usr/bin/env python
import cli

print("*** ZTP: applying base configuration ***")

cli.configurep(
    [
{lines}    ]
)

cli.executep("copy running-config startup-config")
print("*** ZTP: done ***")
"""

    def dhcp_options(self, url: str) -> list[dict]:
        return [{"name": "boot-file-name", "data": url}]


#: One per ZtpMethod; add one with every new method.
BOOTSTRAPS: dict[ZtpMethod, ZtpBootstrap] = {
    bootstrap.method: bootstrap for bootstrap in (CiscoIosxePythonBootstrap(),)
}

__all__ = ["BOOTSTRAPS", "CiscoIosxePythonBootstrap", "ZtpBootstrap"]
