from acex_devkit.models.workflows import WorkflowStepResult, WorkflowWaitJob

#: A workflow run: orchestrated, never queued itself.
WORKFLOW_RUN = "acex.operations.workflow"

#: Steps on nodes: a batch of one job per node, under the run.
WORKFLOW_NODE_STEPS = {step_type: f"{WORKFLOW_RUN}.{step_type}" for step_type in ("execute", "action", "probe")}

#: Steps that run as one job. A probe without nodes pings one address; a wait is run by the backend.
WORKFLOW_ONCE_STEPS = {
    **{step_type: f"{WORKFLOW_RUN}.{step_type}" for step_type in ("compute", "assert", "condition", "wait")},
    "probe": f"{WORKFLOW_RUN}.probe.address",
}


class WorkflowWait:
    """A wait's job, run by the backend once its time has come: there is nothing left to do but say so."""

    @staticmethod
    def elapsed(job) -> WorkflowStepResult:
        data = WorkflowWaitJob.model_validate(job.data)
        return WorkflowStepResult(result={"seconds": data.seconds, **({"dry_run": True} if data.dry_run else {})})
