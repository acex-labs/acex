import logging
import os

import httpx
from acex.models.bug_report import BugReportCreate

logger = logging.getLogger("acex.bug_report.slack")

_SEVERITY_EMOJI = {
    "low": "🟡",
    "medium": "🟠",
    "high": "🔴",
    "critical": "🚨",
}


def _build_blocks(payload: BugReportCreate, reporter: str) -> list[dict]:
    emoji = _SEVERITY_EMOJI.get(payload.severity, "⚪")
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} Bug Report: {payload.title}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Severity:*\n{payload.severity.upper()}"},
                {"type": "mrkdwn", "text": f"*Reporter:*\n{reporter}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Description:*\n{payload.description}"},
        },
    ]
    if payload.steps:
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Steps to reproduce:*\n{payload.steps}"}}
        )
    if payload.page_url:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Page:* {payload.page_url}"}})
    return blocks


async def dispatch(
    payload: BugReportCreate,
    reporter_id: str,
    reporter_email: str | None,
    *,
    webhook_url: str | None = None,
) -> bool:
    """Post a bug report to Slack. Returns True if sent, False if not configured."""
    url = webhook_url or os.getenv("SLACK_BUG_REPORT_WEBHOOK")
    if not url:
        logger.warning("SLACK_BUG_REPORT_WEBHOOK not set — skipping Slack dispatch")
        return False

    reporter = reporter_email or reporter_id
    blocks = _build_blocks(payload, reporter)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json={"blocks": blocks})
        resp.raise_for_status()

    return True
