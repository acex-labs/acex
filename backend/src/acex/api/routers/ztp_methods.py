from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex.ztp import UnknownNed
from acex_devkit.models.ztp import ZtpMethod, ZtpMethodResponse, ZtpMethodUpdate
from fastapi import APIRouter, Depends, HTTPException, status


def _editor(user: dict) -> str:
    """Who changed it: a readable name if the token has one, else its subject."""
    return user.get("preferred_username") or user.get("sub") or "anonymous"


def create_router(automation_engine):
    # Not under /ztp: everything there is public so a factory-default device
    # can fetch its bootstrap, and these choices must not be.
    router = APIRouter(prefix=f"{BASE_URL}/ztp_methods", tags=["Ztp"])
    methods = automation_engine.ztp_methods

    @router.get("", response_model=list[ZtpMethodResponse])
    def list_methods():
        return methods.list_methods()

    @router.get("/{method}", response_model=ZtpMethodResponse)
    def get_method(method: ZtpMethod):
        return methods.get(method)

    @router.put("/{method}", response_model=ZtpMethodResponse)
    def update_method(
        method: ZtpMethod,
        payload: ZtpMethodUpdate,
        user: dict = Depends(_auth.get_current_user),  # noqa: B008
    ):
        try:
            return methods.update(method, payload, updated_by=_editor(user))
        except UnknownNed as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return router
