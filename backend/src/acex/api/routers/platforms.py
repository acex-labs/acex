"""The platform catalog, and the hardware models an installation has enabled. See `acex.platforms`."""

from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex.platforms import PlatformCatalogBuilder, UnknownHardwareModel
from acex_devkit.models.platform_catalog import PlatformCatalog
from fastapi import APIRouter, Depends, HTTPException, status


def _editor(user: dict) -> str:
    """Who changed it: a readable name if the token has one, else its subject."""
    return user.get("preferred_username") or user.get("sub") or "anonymous"


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/platforms", tags=["Inventory"])
    hardware_models = automation_engine.hardware_models
    builder = PlatformCatalogBuilder(hardware_models)

    @router.get("", response_model=PlatformCatalog)
    def list_platforms():
        """Vendors, hardware models and operating systems we have declarations for; per model, the operating
        systems an installed NED supports on it and whether the installation has it enabled."""
        return builder.build()

    # A model name may hold a slash (CISCO1941/K9), so it is the rest of the path.
    @router.put("/enabled_models/{hardware_model:path}", status_code=status.HTTP_204_NO_CONTENT)
    def enable_hardware_model(
        hardware_model: str,
        user: dict = Depends(_auth.get_current_user),  # noqa: B008
    ):
        try:
            hardware_models.enable(hardware_model, enabled_by=_editor(user))
        except UnknownHardwareModel as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @router.delete("/enabled_models/{hardware_model:path}", status_code=status.HTTP_204_NO_CONTENT)
    def disable_hardware_model(hardware_model: str):
        hardware_models.disable(hardware_model)

    return router
