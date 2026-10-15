"""Devices that called in: every bootstrap fetch starts a discovery job, grouped here by IP.

This is the part of ZTP before review: who has fetched a bootstrap, and whether
a worker has found out what it is.
"""

from collections import defaultdict

from acex.models.job import Job, JobState
from acex.models.ztp_discovery import ZtpDiscovery
from acex_devkit.models.pagination import PaginatedResponse
from acex_devkit.models.ztp import ZtpCall, ZtpCallAttempt, ZtpCallStage, ZtpDiscoverData
from sqlmodel import select

#: The discovery job type. By name: acex.jobs registers it with a hook from this package.
_ZTP_DISCOVER = "acex.ztp.discover"

_STAGES = {
    JobState.queued: ZtpCallStage.waiting,
    JobState.running: ZtpCallStage.discovering,
    JobState.failed: ZtpCallStage.failed,
    JobState.cancelled: ZtpCallStage.failed,
    JobState.succeeded: ZtpCallStage.reported,
}


class ZtpCallNotFound(LookupError):
    pass


class ZtpCallManager:
    def __init__(self, db_manager, jobs):
        self.db = db_manager
        self.jobs = jobs

    def list_calls(
        self,
        *,
        stage: ZtpCallStage | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse[ZtpCall]:
        """Devices that called in, most recently seen first."""
        session = next(self.db.get_session())
        try:
            calls = self._calls(session)
        finally:
            session.close()
        if stage is not None:
            calls = [call for call in calls if call.stage == stage]
        return PaginatedResponse(items=calls[offset : offset + limit], total=len(calls), limit=limit, offset=offset)

    def retry(self, source_ip: str, *, created_by: str) -> ZtpCall:
        """Queue discovery of the device at `source_ip` again, the way it last called in."""
        session = next(self.db.get_session())
        try:
            call = next((call for call in self._calls(session) if call.source_ip == source_ip), None)
        finally:
            session.close()
        if call is None:
            raise ZtpCallNotFound(f"No device has called in from {source_ip}.")
        # Raises MessagingNotConfigured or JobPublishError for the caller to answer.
        self.jobs.enqueue(_ZTP_DISCOVER, {"ip": source_ip, "method": call.method}, created_by=created_by)
        return self._call(source_ip)

    def _call(self, source_ip: str) -> ZtpCall:
        session = next(self.db.get_session())
        try:
            return next(call for call in self._calls(session) if call.source_ip == source_ip)
        finally:
            session.close()

    def _calls(self, session) -> list[ZtpCall]:
        jobs = session.exec(
            select(Job)
            .where(Job.type == _ZTP_DISCOVER, Job.parent_id.is_(None))
            .order_by(Job.created_at.desc(), Job.id.desc())
        ).all()
        if not jobs:
            return []
        discoveries = {
            d.job_id: d
            for d in session.exec(select(ZtpDiscovery).where(ZtpDiscovery.job_id.in_([j.id for j in jobs]))).all()
        }

        by_ip: dict[str, list[tuple[Job, ZtpDiscoverData]]] = defaultdict(list)
        for job in jobs:
            data = ZtpDiscoverData.model_validate(job.data)
            by_ip[str(data.ip)].append((job, data))

        calls = []
        for ip, entries in by_ip.items():
            latest_job, latest_data = entries[0]
            attempts = [_attempt(job, discoveries.get(job.id)) for job, _ in entries]
            calls.append(
                ZtpCall(
                    source_ip=ip,
                    method=latest_data.method,
                    stage=_STAGES[latest_job.state],
                    last_seen=latest_job.created_at,
                    attempts=attempts,
                )
            )
        return calls


def _attempt(job: Job, discovery: ZtpDiscovery | None) -> ZtpCallAttempt:
    return ZtpCallAttempt(
        job_id=job.id,
        state=job.state,
        attempts=job.attempts,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        discovery_id=discovery.id if discovery else None,
        serial_number=discovery.serial_number if discovery else None,
        review_status=discovery.review_status if discovery else None,
    )
