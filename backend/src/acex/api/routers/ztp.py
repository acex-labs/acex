from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from acex.constants import BASE_URL


def render_cisco_iosxe(hostname, domain_name, username, password):
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
    return content


CONFIG_GENERATORS = {"cisco_iosxe": render_cisco_iosxe}


async def get_ztp_config(
    hostname: str,
    domain_name: str,
    os_type: str,
    username: str,
    password: str,
):
    generator = CONFIG_GENERATORS.get(os_type)
    if generator is None:
        raise HTTPException(status_code=404, detail="Unsupported os type")

    # Generera innehåll dynamiskt
    content = generator(hostname, domain_name, username, password)

    return Response(
        content=content,
        media_type="application/x-python",
        headers={"Content-Disposition": "attachment; filename=ztp.py"},
    )


def list_os_types():
    return list(CONFIG_GENERATORS.keys())


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/ztp")
    tags = ["Ztp"]
    router.add_api_route("", list_os_types, methods=["GET"], tags=tags, response_model=list[str])
    router.add_api_route("/init_config/{os_type}/ztp.py", get_ztp_config, methods=["GET"], tags=tags)
    return router
