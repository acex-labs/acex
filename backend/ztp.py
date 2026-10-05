#!/usr/bin/env python
import cli

print("*** ZTP: applying base configuration ***")

cli.configurep(
    [
        f"hostname acex-ztp-init-device",
        f"ip domain name example.com",
        f"username cisco privilege 15 secret 0 Cisco123",
        "crypto key generate rsa modulus 2048",
        "ip ssh version 2",
        "line vty 0 15",
        "transport input ssh",
        "login local",
        "end",
    ]
)

cli.executep("copy running-config startup-config")
print("*** ZTP: done ***")
