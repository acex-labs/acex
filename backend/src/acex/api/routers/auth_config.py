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
        """What the API lets a caller do, as this installation is set up: the permissions that routes need, the modes
        of the checks, where in the token the roles are read and, when the settings name roles, what each holds. For
        whoever makes the roles in the identity provider."""
        return _auth.authorization_overview()

    return router
