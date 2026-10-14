from acex.constants import BASE_URL
from fastapi import APIRouter, Request


def create_router(automation_engine):
    # Not under /ztp, which is public for factory-default devices.
    router = APIRouter(prefix=f"{BASE_URL}/ztp_dhcp", tags=["Ztp"])
    kea = automation_engine.ztp_kea

    @router.get("/kea", response_model=dict)
    def kea_config(request: Request):
        """The Kea DHCPv4 config for ZTP. Bootstrap URLs use the address this request reached acex on."""
        return kea.render(str(request.base_url))

    return router
