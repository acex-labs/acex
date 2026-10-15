from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex.jobs import JobPublishError
from acex.messaging import MessagingNotConfigured
from acex.ztp import ZtpNodeConflict, ZtpNodeNotFound
from acex_devkit.models.pagination import PaginatedResponse
from acex_devkit.models.ztp import ZtpNodeDetail, ZtpPipelineNode, ZtpPipelineSummary, ZtpStage
from fastapi import APIRouter, Depends, HTTPException, Query, status


def _actor(user: dict) -> str:
    return user.get("preferred_username") or user.get("sub") or "anonymous"


def create_router(automation_engine):
    # Not under /ztp: everything there is public so a factory-default device
    # can fetch its bootstrap, and this is for operators.
    router = APIRouter(prefix=f"{BASE_URL}/ztp_nodes", tags=["Ztp"])
    pipeline = automation_engine.ztp_pipeline

    @router.get("", response_model=PaginatedResponse[ZtpPipelineNode])
    def list_nodes(
        stage: ZtpStage | None = None,
        stalled: bool | None = None,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ):
        """Nodes in the ZTP pipeline, stalled and failed first. Filter by `stage` for any stage."""
        return pipeline.list_nodes(stage=stage, stalled=stalled, limit=limit, offset=offset)

    @router.get("/summary", response_model=ZtpPipelineSummary)
    def summary():
        """Every node counted once by its ZTP stage, how many are stalled, and approved assets waiting for a node."""
        return pipeline.summary()

    @router.get("/{node_id}", response_model=ZtpNodeDetail)
    def get_node(node_id: int):
        """Where one node stands in ZTP, with the discoveries of its serial and its provisioning jobs."""
        return _act(lambda: pipeline.get(node_id))

    @router.post("/{node_id}/enroll", response_model=ZtpNodeDetail)
    def enroll(node_id: int, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Take the node into ZTP. Its stage then follows its asset until provisioning starts."""
        return _act(lambda: pipeline.enroll(node_id, by=_actor(user)))

    @router.post("/{node_id}/provision", response_model=ZtpNodeDetail)
    def provision(node_id: int, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Start provisioning a ready node: a provisioning job is queued for a worker.

        Without a broker the node stays ready: 503 if none is configured, 502 if it could not be reached.
        """
        return _act(lambda: pipeline.provision(node_id, by=_actor(user)))

    @router.post("/{node_id}/cancel", response_model=ZtpNodeDetail)
    def cancel(node_id: int, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Take the node out of ZTP, back to its status before it was enrolled.

        A node whose provisioning job was running is left failed: its device may be partly configured.
        """
        return _act(lambda: pipeline.cancel(node_id, by=_actor(user)))

    @router.post("/{node_id}/reset", response_model=ZtpNodeDetail)
    def reset(node_id: int, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Step a provisioning or failed node back to enrolled; any provisioning job is cancelled."""
        return _act(lambda: pipeline.reset(node_id, by=_actor(user)))

    def _act(action):
        try:
            return action()
        except ZtpNodeNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ZtpNodeConflict as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except MessagingNotConfigured as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        except JobPublishError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return router
