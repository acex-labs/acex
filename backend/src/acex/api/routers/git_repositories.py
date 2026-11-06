"""Git repositories that ConfigMaps are read from. For administrators only: a ConfigMap is code the backend
runs, so whoever can point it at a repository can run code on it."""

from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex.git_sync import GitRepositoryConflict, GitRepositoryNotFound
from acex_devkit.models.git_repository import GitRepositoryCreate, GitRepositoryResponse, GitRepositoryUpdate
from fastapi import APIRouter, Depends, HTTPException, Response, status


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
    role = automation_engine.settings.git_sync.admin_role
    admin = _auth.require_role(role) if role else _auth.get_current_user
    router = APIRouter(prefix=f"{BASE_URL}/git_repositories", tags=["Git sync"])
    manager = automation_engine.git_sync

    @router.get("", response_model=list[GitRepositoryResponse])
    def list_repositories(_: dict = Depends(admin)):  # noqa: B008
        """Every repository and how its last sync went. `config_maps` are those loaded by the process that
        answered."""
        return manager.repositories()

    @router.post("", response_model=GitRepositoryResponse, status_code=status.HTTP_201_CREATED)
    def create_repository(payload: GitRepositoryCreate, user: dict = Depends(admin)):  # noqa: B008
        """Add a repository and sync it at once; `last_error` says if that failed."""
        try:
            return manager.create(payload, created_by=_who(user))
        except _EXPECTED as exc:
            raise _http(exc) from exc

    @router.get("/{repo_id}", response_model=GitRepositoryResponse)
    def get_repository(repo_id: int, _: dict = Depends(admin)):  # noqa: B008
        try:
            return manager.repository(repo_id)
        except _EXPECTED as exc:
            raise _http(exc) from exc

    @router.patch("/{repo_id}", response_model=GitRepositoryResponse)
    def update_repository(repo_id: int, payload: GitRepositoryUpdate, user: dict = Depends(admin)):  # noqa: B008
        """Change a repository. A change to what is checked out loads it again at once."""
        try:
            return manager.update(repo_id, payload, updated_by=_who(user))
        except _EXPECTED as exc:
            raise _http(exc) from exc

    @router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_repository(repo_id: int, _: dict = Depends(admin)):  # noqa: B008
        """Delete a repository; its ConfigMaps are no longer used."""
        try:
            manager.delete(repo_id)
        except _EXPECTED as exc:
            raise _http(exc) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{repo_id}/sync", response_model=GitRepositoryResponse)
    def sync_repository(repo_id: int, _: dict = Depends(admin)):  # noqa: B008
        """Fetch and load the branch's latest commit now, even if it was loaded (or failed) before."""
        try:
            return manager.sync(repo_id, force=True)
        except _EXPECTED as exc:
            raise _http(exc) from exc

    return router
