"""What changed, and what is planned: the data behind Settings > What's new."""

import gzip
import hashlib
from pathlib import Path

from acex.changelog import ChangelogResponse, ChangelogService
from acex.constants import BASE_URL
from fastapi import APIRouter, Request, Response


def _accepts_gzip(header: str | None) -> bool:
    """`Accept-Encoding: gzip, deflate` or `*`, unless the client gives it a quality of 0."""
    for part in (header or "").split(","):
        name, _, params = part.partition(";")
        if name.strip().lower() not in ("gzip", "*"):
            continue
        quality = params.strip().lower().removeprefix("q=")
        try:
            return float(quality) > 0 if params.strip().lower().startswith("q=") else True
        except ValueError:
            return True
    return False


def _matches(header: str | None, etag: str) -> bool:
    """`If-None-Match` names this version of the answer (or any version, with `*`)."""
    candidates = {item.strip() for item in (header or "").split(",")}
    return "*" in candidates or etag in candidates


def create_router(automation_engine):
    router = APIRouter(prefix=BASE_URL, tags=["System"])
    settings = automation_engine.settings
    service = ChangelogService(
        extra_dir=Path(settings.changelog.extra_dir) if settings.changelog.extra_dir else None,
    )
    compressed: dict[str, bytes] = {}

    @router.get("/changelog", response_model=ChangelogResponse)
    def changelog(request: Request):
        """Release notes of the backend and of every installed component that publishes them, plus planned work.

        Deployment-specific notes (ACEX_CHANGELOG_EXTRA_DIR) come as their own sections after the product.
        The answer is a few hundred kilobytes that change only when a package is updated or a deployment edits
        its notes, so it is sent compressed and with an `ETag`: asking again with `If-None-Match` costs a 304.
        """
        notes = service.changelog()
        body = notes.model_dump_json().encode()
        # What the notes say, not when they were read: `generated_at` would make every answer a new one.
        digest = hashlib.sha256(notes.model_dump_json(exclude={"generated_at"}).encode()).hexdigest()
        etag = f'W/"{digest[:32]}"'
        headers = {"ETag": etag, "Cache-Control": "private, no-cache", "Vary": "Accept-Encoding"}

        if _matches(request.headers.get("if-none-match"), etag):
            return Response(status_code=304, headers=headers)
        if _accepts_gzip(request.headers.get("accept-encoding")):
            if etag not in compressed:
                compressed.clear()
                compressed[etag] = gzip.compress(body, compresslevel=6)
            return Response(
                compressed[etag],
                media_type="application/json",
                headers={**headers, "Content-Encoding": "gzip"},
            )
        return Response(body, media_type="application/json", headers=headers)

    return router
