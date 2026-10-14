from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex.ztp import InvalidDhcpScope, ZtpDhcpScopeNotFound
from acex_devkit.models.ztp import ZtpDhcpScopeCreate, ZtpDhcpScopeResponse, ZtpDhcpScopeUpdate
from fastapi import APIRouter, Depends, HTTPException, status


def _editor(user: dict) -> str:
    """Who changed it: a readable name if the token has one, else its subject."""
    return user.get("preferred_username") or user.get("sub") or "anonymous"


def create_router(automation_engine):
    # Not under /ztp, which is public for factory-default devices.
    router = APIRouter(prefix=f"{BASE_URL}/ztp_dhcp_scopes", tags=["Ztp"])
    scopes = automation_engine.ztp_dhcp_scopes

    @router.get("", response_model=list[ZtpDhcpScopeResponse])
    def list_scopes():
        return scopes.list_scopes()

    @router.post("", response_model=ZtpDhcpScopeResponse, status_code=status.HTTP_201_CREATED)
    def create_scope(
        payload: ZtpDhcpScopeCreate,
        user: dict = Depends(_auth.get_current_user),  # noqa: B008
    ):
        try:
            return scopes.create(payload, updated_by=_editor(user))
        except InvalidDhcpScope as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    @router.patch("/{id}", response_model=ZtpDhcpScopeResponse)
    def update_scope(
        id: int,
        payload: ZtpDhcpScopeUpdate,
        user: dict = Depends(_auth.get_current_user),  # noqa: B008
    ):
        try:
            return scopes.update(id, payload, updated_by=_editor(user))
        except ZtpDhcpScopeNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except InvalidDhcpScope as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    @router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_scope(id: int):
        try:
            scopes.delete(id)
        except ZtpDhcpScopeNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return router
