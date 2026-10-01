from fastapi import APIRouter
from fastapi.responses import Response
from acex.constants import BASE_URL


async def get_ztp_config(
    hostname: str,
    domain_name: str,
    username: str = "admin",
    password: str = "Cisco123",
    device_type: str = "switch",
):
    # Generera innehåll dynamiskt
    content = f"""#!/usr/bin/env python
import cli

print("*** ZTP: applying base configuration ***")

cli.configurep(
    [
        f"hostname {hostname}",
        f"ip domain name {domain_name}",
        f"username {username} privilege 15 secret 0 {password}",
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
"""

    return Response(
        content=content,
        media_type="application/x-python",
        headers={"Content-Disposition": "attachment; filename=ztp.py"},
    )


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/ztp")
    router.add_api_route("/init_config/switch/ztp.py", get_ztp_config, methods=["GET"])
    return router
