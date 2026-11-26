from acex.api import auth as _auth
from acex.constants import BASE_URL
from fastapi import APIRouter


def create_router(automation_engine):
    router = APIRouter(prefix=BASE_URL, tags=["Auth"])

    @router.get("/auth/config")
    def get_auth_config():
        if not _auth.OIDC_ISSUER_URL:
            return {"enabled": False}
        return {
            "enabled": True,
            "authority": _auth.OIDC_ISSUER_URL,
            "client_id": _auth.OIDC_AUDIENCE,
        }

    @router.get("/auth/permissions")
    def get_permissions():
        """What the API lets a caller do and which roles hold it, as this installation is set up: the permissions each
        route needs, the roles of the settings with the permissions they hold, the modes of the checks and where in the
        token the roles are read. For whoever makes the roles in the identity provider."""
        return _auth.authorization_overview()

    return router
