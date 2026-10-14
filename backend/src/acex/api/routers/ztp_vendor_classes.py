from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex.ztp import AmbiguousVendorClass, VendorClassExists, ZtpVendorClassNotFound
from acex_devkit.models.ztp import ZtpVendorClassCreate, ZtpVendorClassResponse, ZtpVendorClassUpdate
from fastapi import APIRouter, Depends, HTTPException, status


def _editor(user: dict) -> str:
    """Who changed it: a readable name if the token has one, else its subject."""
    return user.get("preferred_username") or user.get("sub") or "anonymous"


def create_router(automation_engine):
    # Not under /ztp, which is public for factory-default devices.
    router = APIRouter(prefix=f"{BASE_URL}/ztp_vendor_classes", tags=["Ztp"])
    vendor_classes = automation_engine.ztp_vendor_classes

    @router.get("", response_model=list[ZtpVendorClassResponse])
    def list_vendor_classes():
        return vendor_classes.list_vendor_classes()

    @router.post("", response_model=ZtpVendorClassResponse, status_code=status.HTTP_201_CREATED)
    def create_vendor_class(
        payload: ZtpVendorClassCreate,
        user: dict = Depends(_auth.get_current_user),  # noqa: B008
    ):
        try:
            return vendor_classes.create(payload, updated_by=_editor(user))
        except (VendorClassExists, AmbiguousVendorClass) as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    @router.patch("/{id}", response_model=ZtpVendorClassResponse)
    def update_vendor_class(
        id: int,
        payload: ZtpVendorClassUpdate,
        user: dict = Depends(_auth.get_current_user),  # noqa: B008
    ):
        try:
            return vendor_classes.update(id, payload, updated_by=_editor(user))
        except ZtpVendorClassNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except (VendorClassExists, AmbiguousVendorClass) as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    @router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_vendor_class(id: int):
        try:
            vendor_classes.delete(id)
        except ZtpVendorClassNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return router
