from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex.ztp import ReviewConflict, ZtpDiscoveryNotFound
from acex_devkit.models.pagination import PaginatedResponse
from acex_devkit.models.ztp import (
    ZtpApproveRequest,
    ZtpBulkApprove,
    ZtpBulkReject,
    ZtpBulkResult,
    ZtpDiscoveryResponse,
    ZtpReviewStatus,
)
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status


def _reviewer(user: dict) -> str:
    """Who reviewed: a readable name if the token has one, else its subject."""
    return user.get("preferred_username") or user.get("sub") or "anonymous"


def create_router(automation_engine):
    # Not under /ztp: everything there is public so a factory-default device
    # can fetch its bootstrap, and reviewing what devices report must not be.
    router = APIRouter(prefix=f"{BASE_URL}/ztp_discoveries", tags=["Ztp"])
    discoveries = automation_engine.ztp_discoveries

    @router.get("", response_model=PaginatedResponse[ZtpDiscoveryResponse])
    def list_discoveries(
        review_status: ZtpReviewStatus | None = None,
        asset_id: int | None = None,
        serial_number: str | None = None,
        source_ip: str | None = None,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ):
        return discoveries.list_discoveries(
            review_status=review_status,
            asset_id=asset_id,
            serial_number=serial_number,
            source_ip=source_ip,
            limit=limit,
            offset=offset,
        )

    @router.post("/approve", response_model=ZtpBulkResult)
    def approve_many(body: ZtpBulkApprove, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Approve many discoveries; each one that cannot be approved is skipped with a reason.

        With `dry_run`, nothing is written and the answer says what would happen.
        """
        return discoveries.approve_many(body.items, reviewed_by=_reviewer(user), dry_run=body.dry_run)

    @router.post("/reject", response_model=ZtpBulkResult)
    def reject_many(body: ZtpBulkReject, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        return discoveries.reject_many(body.discovery_ids, reviewed_by=_reviewer(user))

    @router.get("/{discovery_id}", response_model=ZtpDiscoveryResponse)
    def get_discovery(discovery_id: int):
        try:
            return discoveries.get(discovery_id)
        except ZtpDiscoveryNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @router.post("/{discovery_id}/approve", response_model=ZtpDiscoveryResponse)
    def approve(
        discovery_id: int,
        body: ZtpApproveRequest | None = Body(default=None),  # noqa: B008
        user: dict = Depends(_auth.get_current_user),  # noqa: B008
    ):
        """Trust the device's identity: the asset with its serial is created or updated as proposed.

        No node changes; provisioning is a step of its own.
        """
        proposal_hash = body.proposal_hash if body is not None else None
        return _review(lambda **kw: discoveries.approve(discovery_id, proposal_hash=proposal_hash, **kw), user)

    @router.post("/{discovery_id}/reject", response_model=ZtpDiscoveryResponse)
    def reject(discovery_id: int, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Distrust what the device reported. Nothing else changes."""
        return _review(lambda **kw: discoveries.reject(discovery_id, **kw), user)

    def _review(action, user: dict) -> ZtpDiscoveryResponse:
        try:
            return action(reviewed_by=_reviewer(user))
        except ZtpDiscoveryNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ReviewConflict as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return router
