from typing import Literal

from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex.messaging import MessagingNotConfigured
from acex.operations import ACTIONS, EXECUTE, PATCH_RENDER, Action
from acex.operations.runs import OperationRuns
from acex.plugins.neds.manager import NEDManager
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.config_tree import ConfigTreeNode
from acex_devkit.models.operations import ExecuteRequest, PatchApplyRequest, PatchRenderRequest, Run, RunReport
from acex_devkit.models.pagination import PaginatedResponse
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response


def _who(user: dict) -> str:
    return user.get("preferred_username") or user.get("sub") or "anonymous"


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/operations", tags=["Operations"])
    runs = OperationRuns(automation_engine.jobs, automation_engine.inventory.node_instances, NEDManager())

    async def order(ordering) -> Run:
        try:
            return await ordering
        except MessagingNotConfigured as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    tree = ComposedConfiguration.tree()

    @router.get("/patch/tree", response_model=ConfigTreeNode)
    def config_tree():
        """The shape of the configuration tree a patch's path walks: branches, components, keyed collections of
        components with the fields of each entry, and attributes."""
        return tree

    @router.post("/patch/render", response_model=Run, status_code=status.HTTP_202_ACCEPTED)
    async def render_patch(request: PatchRenderRequest, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Render on each node the patch that brings its configuration at `paths` to the desired state, from a
        live read; with `prune`, removing what desired doesn't declare there too. No paths is the whole tree.
        Nothing is sent: the run is the plan a patch apply sends. Every node's NED must support get_config and
        apply."""
        return await order(runs.order(PATCH_RENDER, request, _who(user)))

    @router.post("/patch/apply", response_model=Run, status_code=status.HTTP_202_ACCEPTED)
    async def apply_patch(request: PatchApplyRequest, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Send a plan's patches to some of its nodes. Each node is read live again and patched only if it
        still renders the plan's patch, then read once more to verify."""
        return await order(runs.apply_patch(request, _who(user)))

    @router.post("/execute", response_model=Run, status_code=status.HTTP_202_ACCEPTED)
    async def execute(request: ExecuteRequest, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Run raw commands on each node, in order, in one session per node. Each node's output is masked
        by its NED. Every node's NED must support execute."""
        return await order(runs.order(EXECUTE, request, _who(user)))

    def action_route(action: Action):
        async def run_action(request: action.request, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
            return await order(runs.order(action, request, _who(user)))

        run_action.__doc__ = f"Run {action.name} on each node. Every node's NED must support {action.name}."
        return run_action

    for action in ACTIONS:
        router.add_api_route(
            f"/actions/{action.name}",
            action_route(action),
            methods=["POST"],
            response_model=Run,
            status_code=status.HTTP_202_ACCEPTED,
            name=f"run_{action.name}",
        )

    @router.get("/runs", response_model=PaginatedResponse[Run])
    def list_runs(
        kind: Literal["execute", "actions", "patch"] | None = None,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        """Runs ordered by anyone, newest first."""
        return runs.list(kind, limit, offset)

    @router.get("/runs/{run_id}", response_model=RunReport)
    async def get_run(run_id: int):
        """A run with each node's response, sorted by hostname."""
        return await runs.report(run_id)

    @router.get("/runs/{run_id}/report")
    async def download_report(run_id: int, format: Literal["json", "csv"] = "csv"):
        """The run's report as a file."""
        report = await runs.report(run_id)
        disposition = {"Content-Disposition": f'attachment; filename="run-{run_id}.{format}"'}
        if format == "json":
            return JSONResponse(report.model_dump(mode="json"), headers=disposition)
        return Response(runs.csv(report), media_type="text/csv", headers=disposition)

    return router
