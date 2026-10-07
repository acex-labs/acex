import logging

import httpx
from acex.models.bug_report import BugReportCreate
from acex.settings import SlackBugReportSettings

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
    if payload.screenshots:
        count = len(payload.screenshots)
        noun = "screenshots" if count > 1 else "screenshot"
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"📎 {count} {noun} attached (see file report)"},
            }
        )
    return blocks


async def dispatch(
    payload: BugReportCreate,
    reporter_id: str,
    reporter_email: str | None,
    settings: SlackBugReportSettings,
) -> bool:
    """Post a bug report to Slack. Returns True if sent, False if not configured."""
    if not settings.configured:
        logger.warning("ACEX_BUG_REPORT_SLACK_WEBHOOK_URL not set — skipping Slack dispatch")
        return False

    reporter = reporter_email or reporter_id
    blocks = _build_blocks(payload, reporter)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(settings.webhook_url.get_secret_value(), json={"blocks": blocks})
        resp.raise_for_status()

    return True
