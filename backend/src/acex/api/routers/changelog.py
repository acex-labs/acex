"""What changed, and what is planned: the data behind Settings > What's new."""

from pathlib import Path

from acex.changelog import ChangelogResponse, ChangelogService
from acex.constants import BASE_URL
from fastapi import APIRouter


def create_router(automation_engine):
    router = APIRouter(prefix=BASE_URL, tags=["System"])
    settings = automation_engine.settings
    service = ChangelogService(
        extra_dir=Path(settings.changelog.extra_dir) if settings.changelog.extra_dir else None,
    )

    @router.get("/changelog", response_model=ChangelogResponse)
    def changelog():
        """Release notes of the backend and of every installed component that publishes them, plus planned work.

        Deployment-specific notes (ACEX_CHANGELOG_EXTRA_DIR) come as their own sections after the product.
        """
        return service.changelog()

    return router
