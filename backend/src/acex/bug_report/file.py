import json
import logging
import os
import uuid
from datetime import datetime, timezone

from acex.models.bug_report import BugReportCreate

logger = logging.getLogger("acex.bug_report.file")


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

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{timestamp}_{uuid.uuid4().hex[:8]}.json"
    path = os.path.join(directory, filename)

    report = {
        "timestamp": timestamp,
        "reporter_id": reporter_id,
        "reporter_email": reporter_email,
        **payload.model_dump(),
    }

    with open(path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info("Bug report written to %s", path)
    return True
