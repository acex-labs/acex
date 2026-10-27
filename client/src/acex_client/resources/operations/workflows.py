from acex_devkit.models.workflows import (
    WorkflowArtifacts,
    WorkflowRun,
    WorkflowRunDetail,
    WorkflowRunRequest,
)

from acex_client.resources.base import ActionMixin, Resource, action


class Workflows(Resource, ActionMixin):
    """Workflow runs — `/operations/workflows/*`.

    `client.operations.workflows.start(workflow_id=1, payload=WorkflowRunRequest(mode="evaluate"))` starts a
    run; `get_run()` reads it with every round of every step, `artifacts()` the artifacts its steps left.
    """

    path = "/operations/workflows"
    response_model = WorkflowRunDetail  # type: ignore
    list_model = WorkflowRun  # type: ignore
    create_model = None  # type: ignore
    update_model = None  # type: ignore

    @action("POST", "{workflow_id}/runs")
    def start(self, workflow_id: int, payload: WorkflowRunRequest) -> WorkflowRunDetail: ...

    @action("GET", "runs/{run_id}")
    def get_run(self, run_id: int) -> WorkflowRunDetail: ...

    @action("GET", "runs/{run_id}/artifacts")
    def artifacts(self, run_id: int, names: list[str] | None = None) -> WorkflowArtifacts:
        """Artifacts by name, each from the latest finished round of the step that leaves it, or only those of
        `names`."""

    @action("POST", "runs/{run_id}/continue")
    def resume(self, run_id: int, to_end: bool = False) -> WorkflowRunDetail: ...

    @action("POST", "runs/{run_id}/stop")
    def stop(self, run_id: int) -> WorkflowRunDetail: ...
