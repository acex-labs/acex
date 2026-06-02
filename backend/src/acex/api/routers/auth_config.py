from fastapi import APIRouter
from acex.constants import BASE_URL
from acex.api import auth as _auth


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

    return router
