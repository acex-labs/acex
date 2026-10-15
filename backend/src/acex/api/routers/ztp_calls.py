from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex.jobs import JobPublishError
from acex.messaging import MessagingNotConfigured
from acex.ztp import ZtpCallNotFound
from acex_devkit.models.pagination import PaginatedResponse
from acex_devkit.models.ztp import ZtpCall, ZtpCallStage
from fastapi import APIRouter, Depends, HTTPException, Query, status


def create_router(automation_engine):
    # Not under /ztp: everything there is public so a factory-default device
    # can fetch its bootstrap, and this is for operators.
    router = APIRouter(prefix=f"{BASE_URL}/ztp_calls", tags=["Ztp"])
    calls = automation_engine.ztp_calls

    @router.get("", response_model=PaginatedResponse[ZtpCall])
    def list_calls(
        stage: ZtpCallStage | None = None,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ):
        """Devices that fetched a bootstrap, one per IP, most recently seen first."""
        return calls.list_calls(stage=stage, limit=limit, offset=offset)

    @router.post("/{source_ip}/retry", response_model=ZtpCall)
    def retry(source_ip: str, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Queue discovery of the device again, e.g. after a worker could not log in."""
        try:
            return calls.retry(source_ip, created_by=user.get("sub") or "anonymous")
        except ZtpCallNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except MessagingNotConfigured as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        except JobPublishError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return router
