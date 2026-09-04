import logging

from fastapi import APIRouter, Depends, HTTPException, status

from acex.api import auth as _auth
from acex.bug_report import slack as _slack
from acex.constants import BASE_URL
from acex.models.bug_report import BugReportCreate, BugReportResponse

logger = logging.getLogger("acex.api.bug_reports")


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/bug-reports", tags=["Bug Reports"])

    @router.post("", response_model=BugReportResponse, status_code=status.HTTP_202_ACCEPTED)
    async def submit_bug_report(
        payload: BugReportCreate,
        user: dict = Depends(_auth.get_current_user),
    ):
        reporter_id = user.get("sub")
        if not reporter_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not identify reporter from token",
            )

        reporter_email = user.get("email")
        dispatched_to: list[str] = []

        try:
            if await _slack.dispatch(payload, reporter_id, reporter_email):
                dispatched_to.append("slack")
        except Exception:
            logger.warning("Slack dispatch failed", exc_info=True)

        return BugReportResponse(
            title=payload.title,
            severity=payload.severity,
            reporter_id=reporter_id,
            reporter_email=reporter_email,
            dispatched_to=dispatched_to,
        )

    return router
