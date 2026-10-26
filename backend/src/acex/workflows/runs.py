"""Workflow runs: a run is an orchestrated job. Each round of a step is a job under it, and a step on nodes
has one job per node under that. Workers run the steps and the backend runs waits; the backend decides what
runs next."""

import logging
from datetime import UTC, datetime, timedelta

from acex.jobs import JobConflict, JobManager, JobPublishError
from acex.models.job import Job
from acex.operations import EXECUTE, OPERATIONS, Operation
from acex.operations.runs import OperationRuns
from acex.workflows.job_types import WORKFLOW_NODE_STEPS, WORKFLOW_ONCE_STEPS, WORKFLOW_RUN
from acex.workflows.library import WorkflowLibrary, WorkflowNotFound
from acex.workflows.walk import RoundLimit, Walk
from acex_devkit.models.job import JobResponse, JobState, JobSubjectType
from acex_devkit.models.operations import NodeResponse
from acex_devkit.models.pagination import PaginatedResponse
from acex_devkit.models.workflows import (
    GraphNode,
    RunArtifact,
    WorkflowArtifacts,
    WorkflowNodeJob,
    WorkflowNodeResult,
    WorkflowRun,
    WorkflowRunData,
    WorkflowRunDetail,
    WorkflowRunMode,
    WorkflowStepJob,
    WorkflowStepResult,
    WorkflowStepRun,
    WorkflowWaitJob,
)
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger("acex.workflows")

#: A run in these states is still going: steps finishing in it move it on.
LIVE = (JobState.running, JobState.paused)
#: A step's job in these states hasn't finished.
UNFINISHED = (JobState.scheduled, JobState.queued, JobState.running)


class WorkflowRunError(ValueError):
    """The workflow can't be run as it stands."""


class RunConflict(RuntimeError):
    """The run isn't in a state that allows this."""


class WorkflowRuns:
    def __init__(self, jobs: JobManager, library: WorkflowLibrary, operations: OperationRuns):
        self.jobs = jobs
        self.library = library
        self.operations = operations
        jobs.on_finished.append(self.finished)

    async def start(self, workflow_id: int, mode: WorkflowRunMode, created_by: str) -> WorkflowRunDetail:
        """Start a run of the workflow as it is now. It must have no problems, and each step on nodes needs
        nodes that exist and, for execute and action, whose NED supports the step; nothing is started
        otherwise."""
        workflow = await run_in_threadpool(self.library.workflow, workflow_id)
        problems = [f"{key or 'Workflow'}: {text}" for key, texts in workflow.check.problems.items() for text in texts]
        if problems:
            raise WorkflowRunError(f"The workflow can't run yet. {'; '.join(problems)}")
        hostnames = {}
        for node in workflow.graph.nodes:
            if node.step is None or not node.targets:
                continue
            if node.step.type == "probe":
                targets = [await self.operations.nodes.get(str(node_id)) for node_id in node.targets]
            else:
                targets = await self.operations.supporting(self.operation(node), node.targets)
            for target in targets:
                hostnames[target.id] = target.logical_node.hostname or str(target.id)
        data = WorkflowRunData(
            workflow_id=workflow_id,
            name=workflow.name,
            mode=mode,
            graph=workflow.graph,
            max_rounds=workflow.max_rounds,
            hostnames=hostnames,
        )
        run = await run_in_threadpool(self.jobs.open, WORKFLOW_RUN, data, created_by=created_by)
        await run_in_threadpool(self.begin, run.id)
        return await run_in_threadpool(self.detail, run.id)

    def operation(self, node: GraphNode) -> Operation:
        """The operation an execute or action step runs on each node, for what its NED must support."""
        if node.step.type == "execute":
            return EXECUTE
        operation = OPERATIONS.get(f"acex.operations.actions.{node.step.action}")
        if operation is None:
            raise WorkflowRunError(f"No action {node.step.action}")
        return operation

    def begin(self, run_id: int) -> None:
        starts, doomed = [], []
        with self.jobs.locked(run_id) as run:
            data = WorkflowRunData.model_validate(run.data)
            walk = Walk(data)
            try:
                starts = walk.begin()
                self.settle(run, walk)
            except RoundLimit as exc:
                doomed = self.fail(run, data, str(exc))
            created_by = run.created_by
        self.cancel(run_id, doomed)
        self.launch(run_id, created_by, data, starts)

    def finished(self, job: JobResponse) -> None:
        """Listens for finished jobs: a step whose jobs have all finished moves its run on."""
        if not job.type.startswith(f"{WORKFLOW_RUN}."):
            return
        step = self.jobs.get(job.parent_id) if "node_id" in (job.data or {}) else job
        if step is None or step.state in UNFINISHED:
            return
        ref = WorkflowStepJob.model_validate(step.data)
        starts, doomed = [], []
        with self.jobs.locked(ref.run_id) as run:
            if run is None or run.state not in LIVE:
                return
            data = WorkflowRunData.model_validate(run.data)
            # A step is moved on once: of two of its node jobs finishing at once, the second finds it done.
            if ref.key not in data.active or data.rounds.get(ref.key) != ref.round:
                return
            walk = Walk(data)
            if step.state == JobState.succeeded:
                try:
                    starts = walk.finish(ref.key, self.branch(step))
                    self.settle(run, walk)
                except RoundLimit as exc:
                    starts, doomed = [], self.fail(run, data, str(exc))
            else:
                data.active.remove(ref.key)
                doomed = self.fail(run, data, f"Step {ref.key} {step.state}: {self.why(step, data)}")
            created_by = run.created_by
        self.cancel(ref.run_id, doomed)
        self.launch(ref.run_id, created_by, data, starts)

    def branch(self, step: JobResponse) -> str | None:
        """The side a condition's job took, or None for any other step, or a condition in a dry run."""
        if step.children or not step.type.endswith(".condition"):
            return None
        value = (WorkflowStepResult.model_validate(step.result or {}).result or {}).get("value")
        return None if value is None else "true" if value else "false"

    def resume(self, run_id: int, *, to_end: bool) -> WorkflowRunDetail:
        """Go on with a paused run: one more step, or with `to_end` without pausing again."""
        starts, doomed = [], []
        with self.jobs.locked(run_id) as run:
            if run is None or run.type != WORKFLOW_RUN:
                raise WorkflowNotFound(f"No workflow run {run_id}")
            if run.state != JobState.paused:
                raise RunConflict(f"Run {run_id} is {run.state}, not paused")
            data = WorkflowRunData.model_validate(run.data)
            if to_end:
                data.mode = WorkflowRunMode.run
            walk = Walk(data)
            try:
                starts = walk.resume()
                self.settle(run, walk)
            except RoundLimit as exc:
                doomed = self.fail(run, data, str(exc))
            created_by = run.created_by
        self.cancel(run_id, doomed)
        self.launch(run_id, created_by, data, starts)
        return self.detail(run_id)

    def stop(self, run_id: int, *, stopped_by: str) -> WorkflowRunDetail:
        """Stop the run and every job in it not yet finished, a wait included."""
        self.detail(run_id)
        try:
            self.jobs.cancel(run_id, cancelled_by=stopped_by)
        except JobConflict as exc:
            raise RunConflict(str(exc)) from exc
        return self.detail(run_id)

    def delete(self, run_id: int) -> None:
        """Delete a finished run with every job in it, and so every artifact it made."""
        run = self.detail(run_id)
        if run.state in LIVE:
            raise RunConflict(f"Run {run_id} is {run.state}; stop it before deleting it")
        self.jobs.delete(run_id)

    def page(self, workflow_id: int | None, limit: int, offset: int) -> PaginatedResponse[WorkflowRun]:
        """Runs, newest first: of one workflow, or of all."""
        page = self.jobs.list_jobs(
            type=WORKFLOW_RUN,
            subject_type=JobSubjectType.workflow if workflow_id is not None else None,
            subject_id=workflow_id,
            limit=limit,
            offset=offset,
        )
        runs = [self.summary(self.jobs.get(item.id)) for item in page.items]
        return PaginatedResponse(items=runs, total=page.total, limit=limit, offset=offset)

    def detail(self, run_id: int) -> WorkflowRunDetail:
        run = self.jobs.get(run_id)
        if run is None or run.type != WORKFLOW_RUN:
            raise WorkflowNotFound(f"No workflow run {run_id}")
        data = WorkflowRunData.model_validate(run.data)
        return WorkflowRunDetail(
            **self.summary(run).model_dump(),
            graph=data.graph,
            hostnames=data.hostnames,
            active=data.active,
            pending=data.pending,
            branches=data.branches,
            step_runs=[self.step_run(job) for job in self.jobs.children(run_id)],
        )

    def responses(self, run_id: int, job_id: int) -> list[NodeResponse]:
        """What each node answered in one round of a step on nodes, by hostname."""
        run = self.detail(run_id)
        step = self.jobs.get(job_id)
        if step is None or step.parent_id != run_id or not step.children:
            raise WorkflowNotFound(f"No step on nodes {job_id} in run {run_id}")
        responses = [
            NodeResponse(
                node_id=job.subject_id,
                hostname=run.hostnames.get(job.subject_id),
                job_id=job.id,
                state=job.state,
                result=job.result,
                error=job.error,
                finished_at=job.finished_at,
            )
            for job in self.jobs.children(job_id)
        ]
        responses.sort(key=lambda r: (r.hostname is None, r.hostname or "", r.node_id))
        return responses

    def artifacts(self, run_id: int, names: list[str] | None = None) -> WorkflowArtifacts:
        """Artifacts by name, each from the latest finished round of the step that leaves it; `names` limits it
        to those. A step on nodes has the values of the nodes it succeeded on."""
        run = self.detail(run_id)
        producers = run.graph.producers()
        names = list(producers) if names is None else [name for name in names if name in producers]
        keys = {producers[name] for name in names}
        latest: dict[str, JobResponse] = {}
        for job in self.jobs.children(run_id):
            ref = WorkflowStepJob.model_validate(job.data)
            if ref.key in keys and job.state not in UNFINISHED:
                latest[ref.key] = job  # oldest first, so the last one is the latest round
        node_results: dict[str, list[tuple[str, WorkflowNodeResult]]] = {}
        artifacts = {}
        for name in names:
            key = producers[name]
            job = latest.get(key)
            if job is None:
                continue
            round_ = WorkflowStepJob.model_validate(job.data).round
            if run.graph.node(key).on_nodes:
                if key not in node_results:
                    node_results[key] = [
                        (run.hostnames.get(node.subject_id, str(node.subject_id)), self.node_result(node))
                        for node in self.jobs.children(job.id)
                        if node.state == JobState.succeeded
                    ]
                nodes = {host: result.artifacts[name] for host, result in node_results[key] if name in result.artifacts}
                artifacts[name] = RunArtifact(step=key, round=round_, nodes=nodes)
            elif job.state == JobState.succeeded:
                value = WorkflowStepResult.model_validate(job.result or {}).artifacts.get(name)
                if value is not None:
                    artifacts[name] = RunArtifact(step=key, round=round_, **value.model_dump())
        return WorkflowArtifacts(artifacts=artifacts)

    def node_result(self, job: JobResponse) -> WorkflowNodeResult:
        return WorkflowNodeResult.model_validate(job.result or {})

    def summary(self, run: JobResponse) -> WorkflowRun:
        data = WorkflowRunData.model_validate(run.data)
        return WorkflowRun(
            id=run.id,
            workflow_id=data.workflow_id,
            name=data.name,
            mode=data.mode,
            state=run.state,
            error=run.error,
            created_by=run.created_by,
            created_at=run.created_at,
            finished_at=run.finished_at,
        )

    def step_run(self, job: JobResponse) -> WorkflowStepRun:
        ref = WorkflowStepJob.model_validate(job.data)
        result = WorkflowStepResult.model_validate(job.result) if job.result is not None and not job.children else None
        return WorkflowStepRun(
            key=ref.key,
            round=ref.round,
            job_id=job.id,
            state=job.state,
            jobs=job.children,
            result=result,
            error=job.error,
            created_at=job.created_at,
            run_at=job.run_at,
            finished_at=job.finished_at,
        )

    def settle(self, run: Job, walk: Walk) -> None:
        """Set the locked run's state from where its walk stands, and save the walk."""
        if walk.done:
            self.jobs.stamp(run, JobState.succeeded)
        elif not walk.data.active:
            self.jobs.stamp(run, JobState.paused)
        else:
            self.jobs.stamp(run, JobState.running)
        run.data = walk.data.model_dump(mode="json")

    def fail(self, run: Job, data: WorkflowRunData, error: str) -> list[str]:
        """Fail the locked run; returns its steps still active, for `cancel` once the lock is let go."""
        doomed, data.active = data.active, []
        self.jobs.stamp(run, JobState.failed, error=error)
        run.data = data.model_dump(mode="json")
        return doomed

    def cancel(self, run_id: int, keys: list[str]) -> None:
        if not keys:
            return
        for job in self.jobs.children(run_id):
            if job.data["key"] in keys and job.state in UNFINISHED:
                try:
                    self.jobs.cancel(job.id, cancelled_by="system")
                except JobConflict:
                    pass  # it finished meanwhile

    def why(self, step: JobResponse, data: WorkflowRunData) -> str:
        """Why a step didn't succeed: its error, or for a step on nodes, which nodes failed and the first error."""
        if not step.children:
            return step.error or "no reason given"
        failed = [job for job in self.jobs.children(step.id) if job.state != JobState.succeeded]
        hosts = [data.hostnames.get(job.subject_id, str(job.subject_id)) for job in failed]
        first = next((job.error for job in failed if job.error), "no reason given")
        return f"on {', '.join(hosts)} of {sum(step.children.values())} nodes: {first}"

    def launch(self, run_id: int, created_by: str, data: WorkflowRunData, keys: list[str]) -> None:
        """Make the jobs of the steps the walk started. A step that can't be started fails the run."""
        for key in keys:
            node = data.graph.node(key)
            ref = WorkflowStepJob(run_id=run_id, key=key, round=data.rounds[key])
            try:
                if node.on_nodes:
                    items = [WorkflowNodeJob(**ref.model_dump(), node_id=node_id) for node_id in node.targets]
                    job_type = WORKFLOW_NODE_STEPS[node.step.type]
                    self.jobs.enqueue_batch(job_type, items, created_by=created_by, request=ref, parent_id=run_id)
                elif node.step.type == "wait":
                    dry_run = data.mode == WorkflowRunMode.dry_run
                    wait = WorkflowWaitJob(**ref.model_dump(), seconds=node.step.seconds, dry_run=dry_run)
                    run_at = datetime.now(UTC) + timedelta(seconds=0 if dry_run else node.step.seconds)
                    self.jobs.enqueue(
                        WORKFLOW_ONCE_STEPS["wait"], wait, created_by=created_by, parent_id=run_id, run_at=run_at
                    )
                else:
                    job_type = WORKFLOW_ONCE_STEPS[node.step.type]
                    self.jobs.enqueue(job_type, ref, created_by=created_by, parent_id=run_id)
            except JobPublishError:
                pass  # marked failed, which has failed the run already
            except Exception as exc:
                logger.exception(f"Workflow run {run_id}: step {key} could not start")
                self.abort(run_id, f"Step {key} could not start: {exc}")
                return

    def abort(self, run_id: int, error: str) -> None:
        with self.jobs.locked(run_id) as run:
            if run is None or run.state not in LIVE:
                return
            doomed = self.fail(run, WorkflowRunData.model_validate(run.data), error)
        self.cancel(run_id, doomed)
