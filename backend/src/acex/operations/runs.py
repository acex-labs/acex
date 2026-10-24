"""Runs: an operation ordered on a number of nodes, as one job per node under a batch."""

import csv
import io

from acex.jobs import JobManager
from acex.operations.kinds import OPERATIONS, Operation
from acex_devkit.models.job import JobResponse
from acex_devkit.models.operations import NodeResponse, NodeSelection, Run, RunReport
from acex_devkit.models.pagination import PaginatedResponse
from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool

#: Job type prefixes of the run kinds listed apart.
KINDS = {"execute": "acex.operations.execute", "actions": "acex.operations.actions."}


class OperationRuns:
    """Orders runs and reads them back. Only nodes whose NED supports the operation can be in a run."""

    def __init__(self, jobs: JobManager, nodes, neds):
        self.jobs = jobs
        self.nodes = nodes
        self.neds = neds

    async def order(self, operation: Operation, request: NodeSelection, created_by: str) -> Run:
        """Make the run's jobs and publish them. A node that doesn't exist answers 404, and one whose NED
        can't run the operation 422, before any job is made."""
        nodes = [await self.nodes.get(str(node_id)) for node_id in request.node_ids]
        capabilities: dict[str, object] = {}
        unsupported = []
        for node in nodes:
            ned_id = node.asset.ned_id
            if ned_id and ned_id not in capabilities:
                driver = self.neds.get_driver_instance(ned_id)
                capabilities[ned_id] = driver.capabilities if driver is not None else None
            if not operation.supported_by(capabilities.get(ned_id)):
                unsupported.append(node.logical_node.hostname or str(node.id))
        if unsupported:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"No {operation.capability[1]} on the driver of: {', '.join(unsupported)}",
            )
        batch = await run_in_threadpool(
            self.jobs.enqueue_batch,
            operation.job_type,
            operation.items(request),
            created_by=created_by,
            request=request,
        )
        return self.run(batch)

    def run(self, batch: JobResponse) -> Run:
        request = {k: v for k, v in (batch.data or {}).items() if k != "node_ids"}
        return Run(
            id=batch.id,
            type=batch.type,
            state=batch.state,
            jobs=batch.children or {},
            request=request or None,
            created_by=batch.created_by,
            created_at=batch.created_at,
        )

    def list(self, kind: str | None, limit: int, offset: int) -> PaginatedResponse[Run]:
        """Runs, newest first; `kind` is "execute" or "actions"."""
        page = self.jobs.list_jobs(type_prefix=KINDS.get(kind, "acex.operations."), limit=limit, offset=offset)
        runs = [self.run(self.jobs.get(summary.id)) for summary in page.items if summary.children]
        return PaginatedResponse(items=runs, total=page.total, limit=limit, offset=offset)

    async def report(self, run_id: int) -> RunReport:
        batch = self.jobs.get(run_id)
        if batch is None or batch.type not in OPERATIONS or not batch.children:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No run {run_id}")
        jobs = self.jobs.children(run_id)
        hostnames = {node_id: await self.hostname(node_id) for node_id in {job.subject_id for job in jobs}}
        responses = [
            NodeResponse(
                node_id=job.subject_id,
                hostname=hostnames[job.subject_id],
                job_id=job.id,
                state=job.state,
                result=job.result,
                error=job.error,
                finished_at=job.finished_at,
            )
            for job in jobs
        ]
        responses.sort(key=lambda r: (r.hostname is None, r.hostname or "", r.node_id))
        return RunReport(**self.run(batch).model_dump(), responses=responses)

    async def hostname(self, node_id: int) -> str | None:
        try:
            return (await self.nodes.get(str(node_id))).logical_node.hostname
        except HTTPException:
            return None

    def csv(self, report: RunReport) -> str:
        """The report as CSV: one row per node, or per command for raw commands."""
        operation = OPERATIONS[report.type]
        columns = ["hostname", "node_id", "state", *operation.columns, "error", "finished_at"]
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for response in report.responses:
            node = {
                "hostname": response.hostname,
                "node_id": response.node_id,
                "state": response.state,
                "error": response.error,
                "finished_at": response.finished_at.isoformat() if response.finished_at else None,
            }
            for cells in operation.cells(response.result):
                writer.writerow({**node, **cells})
        return out.getvalue()
