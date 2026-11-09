from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex.messaging import MessagingNotConfigured
from acex.workflows.library import WorkflowNotFound
from acex.workflows.runs import RunConflict
from acex_devkit.models.operations import NodeResponse
from acex_devkit.models.pagination import PaginatedResponse
from acex_devkit.models.workflows import (
    WorkflowArtifacts,
    WorkflowCheck,
    WorkflowCreate,
    WorkflowGraph,
    WorkflowResponse,
    WorkflowRun,
    WorkflowRunDetail,
    WorkflowRunRequest,
    WorkflowUpdate,
)
from acex_devkit.workflows.check import WorkflowChecker
from fastapi import APIRouter, Depends, HTTPException, Query, status


def _who(user: dict) -> str:
    return user.get("preferred_username") or user.get("sub") or "anonymous"


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, WorkflowNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, RunConflict):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, MessagingNotConfigured):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))


#: What the routes turn into HTTP errors; anything else is a server error.
_EXPECTED = (WorkflowNotFound, RunConflict, MessagingNotConfigured, ValueError)


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/operations/workflows", tags=["Workflows"])
    library = automation_engine.workflows
    runs = automation_engine.workflow_runs

    @router.post("/check", response_model=WorkflowCheck)
    def check_graph(graph: WorkflowGraph):
        """What keeps a graph from running, what in it is worth a second look, and what each step can read;
        for the builder, as it is drawn."""
        return WorkflowChecker(graph).check()

    # Runs

    @router.get("/runs", response_model=PaginatedResponse[WorkflowRun])
    def list_runs(
        workflow_id: int | None = None,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        """Runs by anyone, newest first: of one workflow, or of all."""
        return runs.page(workflow_id, limit, offset)

    @router.get("/runs/{run_id}", response_model=WorkflowRunDetail)
    def get_run(run_id: int):
        """A run: what it runs, as it was when it started, and every round of every step so far."""
        try:
            return runs.detail(run_id)
        except _EXPECTED as exc:
            raise _http(exc) from exc

    @router.get("/runs/{run_id}/steps/{job_id}", response_model=list[NodeResponse])
    def get_step_responses(run_id: int, job_id: int):
        """What each node answered in one round of a step on nodes, sorted by hostname."""
        try:
            return runs.responses(run_id, job_id)
        except _EXPECTED as exc:
            raise _http(exc) from exc

    @router.get("/runs/{run_id}/artifacts", response_model=WorkflowArtifacts)
    def get_artifacts(run_id: int, names: list[str] | None = Query(None)):  # noqa: B008
        """Artifacts by name, each from the latest finished round of the step that leaves it, or only those of
        `names`. Workers read them to run later steps."""
        try:
            return runs.artifacts(run_id, names)
        except _EXPECTED as exc:
            raise _http(exc) from exc

    @router.post("/runs/{run_id}/continue", response_model=WorkflowRunDetail)
    def continue_run(run_id: int, to_end: bool = False):
        """Go on with a paused run: fire the edges of the steps that finished, then pause again after the
        next ones, or with `to_end` run to the end."""
        try:
            return runs.resume(run_id, to_end=to_end)
        except _EXPECTED as exc:
            raise _http(exc) from exc

    @router.post("/runs/{run_id}/stop", response_model=WorkflowRunDetail)
    def stop_run(run_id: int, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Stop a running or paused run, and every job in it still queued or running."""
        try:
            return runs.stop(run_id, stopped_by=_who(user))
        except _EXPECTED as exc:
            raise _http(exc) from exc

    @router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_run(run_id: int):
        """Delete a finished run with all it made: its jobs, results and artifacts."""
        try:
            runs.delete(run_id)
        except _EXPECTED as exc:
            raise _http(exc) from exc

    # Workflows

    @router.get("", response_model=list[WorkflowResponse])
    def list_workflows():
        """Every saved workflow, by name."""
        return library.workflows()

    @router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
    def create_workflow(payload: WorkflowCreate, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        try:
            return library.create_workflow(payload, created_by=_who(user))
        except _EXPECTED as exc:
            raise _http(exc) from exc

    @router.get("/{workflow_id}", response_model=WorkflowResponse)
    def get_workflow(workflow_id: int):
        try:
            return library.workflow(workflow_id)
        except _EXPECTED as exc:
            raise _http(exc) from exc

    @router.patch("/{workflow_id}", response_model=WorkflowResponse)
    def update_workflow(workflow_id: int, payload: WorkflowUpdate, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        try:
            return library.update_workflow(workflow_id, payload, updated_by=_who(user))
        except _EXPECTED as exc:
            raise _http(exc) from exc

    @router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_workflow(workflow_id: int):
        """Delete a workflow. Its runs are kept, each with its own copy of what it ran."""
        try:
            library.delete_workflow(workflow_id)
        except _EXPECTED as exc:
            raise _http(exc) from exc

    @router.post("/{workflow_id}/runs", response_model=WorkflowRunDetail, status_code=status.HTTP_202_ACCEPTED)
    async def start_run(
        workflow_id: int,
        request: WorkflowRunRequest,
        user: dict = Depends(_auth.get_current_user),  # noqa: B008
    ):
        """Run the workflow as it is now: it must have no problems, and each step on nodes needs nodes that
        exist and can run it. A dry run reaches no device."""
        try:
            return await runs.start(workflow_id, request.mode, _who(user))
        except _EXPECTED as exc:
            raise _http(exc) from exc

    return router
