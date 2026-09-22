import base64
import logging
import os

import httpx
from acex.models.bug_report import BugReportCreate

_IMAGE_EXTS = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}

logger = logging.getLogger("acex.bug_report.ado")

_SEVERITY_PRIORITY = {"low": 4, "medium": 3, "high": 2, "critical": 1}


def _auth_header(pat: str) -> str:
    encoded = base64.b64encode(f":{pat}".encode()).decode()
    return f"Basic {encoded}"


def _work_item_url(org: str, project: str) -> str:
    return f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/$User%20Story?api-version=7.1"


def _parent_url(org: str, project: str, feature_id: int) -> str:
    return f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{feature_id}"


def _build_patch(
    payload: BugReportCreate,
    reporter: str,
    parent_url: str,
) -> list[dict]:
    description_html = (
        f"<b>Reporter:</b> {reporter}<br>"
        f"<b>Severity:</b> {payload.severity}<br><br>"
        f"<b>Description:</b><br>{payload.description}"
    )
    if payload.steps:
        description_html += f"<br><br><b>Steps to reproduce:</b><br>{payload.steps}"
    if payload.page_url:
        description_html += f"<br><br><b>Page:</b> {payload.page_url}"

    return [
        {"op": "add", "path": "/fields/System.Title", "value": f"Bug: {payload.title}"},
        {"op": "add", "path": "/fields/System.Description", "value": description_html},
        {
            "op": "add",
            "path": "/fields/Microsoft.VSTS.Common.Priority",
            "value": _SEVERITY_PRIORITY.get(payload.severity, 2),
        },
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": parent_url,
                "attributes": {"comment": "Bug report feature"},
            },
        },
    ]


async def dispatch(
    payload: BugReportCreate,
    reporter_id: str,
    reporter_email: str | None,
    *,
    pat: str | None = None,
    org: str | None = None,
    project: str | None = None,
    feature_id: int | None = None,
) -> bool:
    """Create a User Story in ADO under the configured feature. Returns True if created."""
    _pat = pat or os.getenv("ADO_SERVICE_PAT")
    _org = org or os.getenv("ADO_ORG")
    _project = project or os.getenv("ADO_PROJECT")
    _feature_id_str = str(feature_id) if feature_id else os.getenv("ADO_BUGFIX_FEATURE_ID")

    if not all([_pat, _org, _project, _feature_id_str]):
        cfg = {"PAT": _pat, "org": _org, "project": _project, "feature_id": _feature_id_str}
        missing = [k for k, v in cfg.items() if not v]
        logger.warning(f"ADO not configured — missing: {missing}")
        return False

    _feature_id = int(_feature_id_str)
    reporter = reporter_email or reporter_id
    patch = _build_patch(payload, reporter, _parent_url(_org, _project, _feature_id))

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            _work_item_url(_org, _project),
            json=patch,
            headers={
                "Authorization": _auth_header(_pat),
                "Content-Type": "application/json-patch+json",
            },
        )
        resp.raise_for_status()

    created_id = resp.json().get("id")
    logger.info(f"ADO work item created: {created_id}")

    if payload.screenshots and created_id:
        await _attach_screenshots(payload.screenshots, created_id, _pat, _org, _project)

    return True


async def _attach_screenshots(
    data_uris: list[str],
    work_item_id: int,
    pat: str,
    org: str,
    project: str,
) -> None:
    attach_base = f"https://dev.azure.com/{org}/{project}/_apis/wit/attachments"
    item_url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{work_item_id}?api-version=7.1"
    auth = _auth_header(pat)

    relations = []
    async with httpx.AsyncClient(timeout=30) as client:
        for i, uri in enumerate(data_uris):
            try:
                header, b64 = uri.split(",", 1)
                mime = header.split(":")[1].split(";")[0]
                ext = _IMAGE_EXTS.get(mime, ".png")
                fname = f"screenshot_{i + 1}{ext}"
                image_bytes = base64.b64decode(b64)

                upload = await client.post(
                    f"{attach_base}?api-version=7.1&fileName={fname}",
                    content=image_bytes,
                    headers={"Authorization": auth, "Content-Type": "application/octet-stream"},
                )
                upload.raise_for_status()
                attachment_url = upload.json().get("url")
                if attachment_url:
                    relations.append({
                        "op": "add",
                        "path": "/relations/-",
                        "value": {
                            "rel": "AttachedFile",
                            "url": attachment_url,
                            "attributes": {"comment": f"Screenshot {i + 1}"},
                        },
                    })
            except Exception:
                logger.warning("Failed to upload ADO screenshot %d", i + 1, exc_info=True)

        if relations:
            patch = await client.patch(
                item_url,
                json=relations,
                headers={"Authorization": auth, "Content-Type": "application/json-patch+json"},
            )
            patch.raise_for_status()
            logger.info("Attached %d screenshot(s) to ADO work item %d", len(relations), work_item_id)
