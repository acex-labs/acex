import asyncio
import logging

from acex.jobs.manager import JobManager

logger = logging.getLogger("acex.jobs")


class JobDispatcher:
    """Starts scheduled jobs when their time comes: a loop in the API that looks every `interval` seconds.
    The jobs table holds what is due, so nothing is lost when the API restarts, and with several API
    processes each due job is still started once."""

    BATCH = 100

    def __init__(self, jobs: JobManager, interval: float = 1.0):
        self.jobs = jobs
        self.interval = interval

    async def run(self) -> None:
        while True:
            try:
                # A full batch means more may be due: take the next one at once.
                while await asyncio.to_thread(self.jobs.dispatch_due, self.BATCH) == self.BATCH:
                    pass
            except Exception:
                logger.exception("Starting scheduled jobs failed")
            await asyncio.sleep(self.interval)
