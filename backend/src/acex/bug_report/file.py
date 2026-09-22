import base64
import json
import logging
import os
import uuid
from datetime import UTC, datetime

from acex.models.bug_report import BugReportCreate

logger = logging.getLogger("acex.bug_report.file")

_IMAGE_EXTS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def _save_screenshots(data_uris: list[str], directory: str, prefix: str) -> list[str]:
    """Decode base64 data URIs and save as image files. Returns saved filenames."""
    saved = []
    for i, uri in enumerate(data_uris):
        try:
            header, b64 = uri.split(",", 1)
            mime = header.split(":")[1].split(";")[0]
            ext = _IMAGE_EXTS.get(mime, ".png")
            fname = f"{prefix}_screenshot_{i + 1}{ext}"
            fpath = os.path.join(directory, fname)
            with open(fpath, "wb") as f:
                f.write(base64.b64decode(b64))
            saved.append(fname)
        except Exception:
            logger.warning("Failed to save screenshot %d", i + 1, exc_info=True)
    return saved


async def dispatch(
    payload: BugReportCreate,
    reporter_id: str,
    reporter_email: str | None,
    *,
    report_dir: str | None = None,
) -> bool:
    """Write a bug report as a JSON file. Returns True if written, False if not configured."""
    directory = report_dir or os.getenv("BUG_REPORT_FILE_DIR")
    if not directory:
        return False

    os.makedirs(directory, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    uid = uuid.uuid4().hex[:8]
    filename = f"{timestamp}_{uid}.json"
    path = os.path.join(directory, filename)

    screenshot_files: list[str] = []
    if payload.screenshots:
        screenshot_files = _save_screenshots(payload.screenshots, directory, f"{timestamp}_{uid}")

    data = payload.model_dump(exclude={"screenshots"})
    report = {
        "timestamp": timestamp,
        "reporter_id": reporter_id,
        "reporter_email": reporter_email,
        **data,
        "screenshot_files": screenshot_files,
    }

    with open(path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info("Bug report written to %s (%d screenshot(s))", path, len(screenshot_files))
    return True
