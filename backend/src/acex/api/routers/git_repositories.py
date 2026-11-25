"""Git repositories that ConfigMaps are read from. Open to every signed-in user, like the rest of the API."""

import logging

from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex.git_sync import GitRepositoryConflict, GitRepositoryNotFound, webhook
from acex_devkit.models.git_repository import GitRepositoryCreate, GitRepositoryResponse, GitRepositoryUpdate
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

logger = logging.getLogger("acex.git_sync")


def _who(user: dict) -> str:
    return user.get("preferred_username") or user.get("sub") or "anonymous"


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, GitRepositoryNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, GitRepositoryConflict):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))


_EXPECTED = (GitRepositoryNotFound, ValueError)


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/git_repositories", tags=["Git sync"])
    manager = automation_engine.git_sync

    @router.get("", response_model=list[GitRepositoryResponse])
    def list_repositories(_: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Every repository and how its last sync went. `config_maps` are those loaded by the process that
        answered."""
        return manager.repositories()

    @router.post("", response_model=GitRepositoryResponse, status_code=status.HTTP_201_CREATED)
    def create_repository(payload: GitRepositoryCreate, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Add a repository and sync it at once; `last_error` says if that failed."""
        try:
            return manager.create(payload, created_by=_who(user))
        except _EXPECTED as exc:
            raise _http(exc) from exc

    @router.get("/{repo_id}", response_model=GitRepositoryResponse)
    def get_repository(repo_id: int, _: dict = Depends(_auth.get_current_user)):  # noqa: B008
        try:
            return manager.repository(repo_id)
        except _EXPECTED as exc:
            raise _http(exc) from exc

    @router.patch("/{repo_id}", response_model=GitRepositoryResponse)
    def update_repository(repo_id: int, payload: GitRepositoryUpdate, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Change a repository. A change to what is checked out loads it again at once."""
        try:
            return manager.update(repo_id, payload, updated_by=_who(user))
        except _EXPECTED as exc:
            raise _http(exc) from exc

    @router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_repository(repo_id: int, _: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Delete a repository; its ConfigMaps are no longer used."""
        try:
            manager.delete(repo_id)
        except _EXPECTED as exc:
            raise _http(exc) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{repo_id}/sync", response_model=GitRepositoryResponse)
    def sync_repository(repo_id: int, _: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Fetch and load the branch's latest commit now, even if it was loaded (or failed) before."""
        try:
            return manager.sync(repo_id, force=True)
        except _EXPECTED as exc:
            raise _http(exc) from exc

    def sync_after_push(repo_id: int) -> None:
        try:
            manager.sync(repo_id)
        except Exception:
            logger.exception(f"Syncing git repository {repo_id} after a webhook failed")

    @router.post("/{repo_id}/webhook", status_code=status.HTTP_202_ACCEPTED)
    async def receive_webhook(repo_id: int, request: Request, background: BackgroundTasks):
        """Sync the repository because its git host says that the branch has a new commit.

        Open without a token, since a git host cannot sign in: the request must carry the secret of the repository,
        the token of its `webhook_credential_id`, as GitLab's `X-Gitlab-Token` or as GitHub's `X-Hub-Signature-256`.
        A push to the branch the repository follows answers 202 and syncs in the background; a ping, a push to another
        ref and any other event answer 200 and do nothing."""
        if int(request.headers.get("content-length") or 0) > webhook.MAX_BODY_BYTES:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="The request is too large")
        body = await request.body()
        if len(body) > webhook.MAX_BODY_BYTES:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="The request is too large")
        target = await run_in_threadpool(manager.webhook, repo_id)
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This repository has no webhook")
        branch, secret = target
        if not webhook.signed_by(secret, request.headers, body):
            logger.warning(f"Webhook for git repository {repo_id} refused: the secret does not match")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="The webhook secret does not match")
        event = webhook.event_of(request.headers, body)
        if event.kind != "push":
            return JSONResponse({"status": "ignored", "reason": f"{event.kind} event"}, status_code=200)
        if event.deleted or event.ref != f"refs/heads/{branch}":
            return JSONResponse({"status": "ignored", "reason": f"not a push to {branch}"}, status_code=200)
        logger.info(f"Webhook for git repository {repo_id}: a push to {branch}, syncing")
        background.add_task(sync_after_push, repo_id)
        return {"status": "sync started"}

    return router
