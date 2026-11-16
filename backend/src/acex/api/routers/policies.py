from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex.policies import SoftwarePolicyConflict, SoftwarePolicyNotFound
from acex_devkit.models.platform import OS, Vendor
from acex_devkit.models.policy import (
    SoftwarePolicyCreate,
    SoftwarePolicyResponse,
    SoftwarePolicyUpdate,
    SoftwareVersionInUse,
)
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError


def _editor(user: dict) -> str:
    """Who changed it: a readable name if the token has one, else its subject."""
    return user.get("preferred_username") or user.get("sub") or "anonymous"


def create_router(automation_engine):
    """Policies the environment is held to, one subresource per policy type."""
    router = APIRouter(prefix=f"{BASE_URL}/policies", tags=["Policies"])
    software = automation_engine.software_policies

    @router.get("/software", response_model=list[SoftwarePolicyResponse])
    def list_software_policies():
        return software.list_policies()

    # Before /software/{id}, which would otherwise take "versions" for an id.
    @router.get("/software/versions", response_model=list[SoftwareVersionInUse])
    def list_versions_in_use(vendor: Vendor, os: OS, hardware_model: str | None = None):
        """The versions assets in the inventory report, newest first: suggestions for what to approve. Without a
        hardware model, every model of the vendor."""
        return software.versions_in_use(vendor, os, hardware_model)

    @router.get("/software/{id}", response_model=SoftwarePolicyResponse)
    def get_software_policy(id: int):
        try:
            return software.get(id)
        except SoftwarePolicyNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @router.post("/software", response_model=SoftwarePolicyResponse, status_code=status.HTTP_201_CREATED)
    def create_software_policy(
        payload: SoftwarePolicyCreate,
        user: dict = Depends(_auth.get_current_user),  # noqa: B008
    ):
        try:
            return software.create(payload, updated_by=_editor(user))
        except SoftwarePolicyConflict as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    @router.patch("/software/{id}", response_model=SoftwarePolicyResponse)
    def update_software_policy(
        id: int,
        payload: SoftwarePolicyUpdate,
        user: dict = Depends(_auth.get_current_user),  # noqa: B008
    ):
        try:
            return software.update(id, payload, updated_by=_editor(user))
        except SoftwarePolicyNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except SoftwarePolicyConflict as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except ValidationError as exc:
            # The rule as changed, checked as a whole: answered like a request that fails validation.
            raise RequestValidationError(exc.errors(include_url=False, include_context=False)) from exc

    @router.delete("/software/{id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_software_policy(id: int):
        try:
            software.delete(id)
        except SoftwarePolicyNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return router
