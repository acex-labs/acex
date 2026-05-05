"""Grafana Sync entrypoint — reconciles ACEX-generated dashboards/datasources to Grafana."""

import os
import sys
import logging

from acex_client.acex.acex import Acex

from acex_grafana_sync.agent import GrafanaAgent
from acex_grafana_sync.grafana_client import GrafanaClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("acex_grafana_sync")


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def main():
    api_url = os.environ.get("ACEX_API_URL")
    grafana_url = os.environ.get("GRAFANA_URL")
    grafana_token = os.environ.get("GRAFANA_TOKEN")
    grafana_user = os.environ.get("GRAFANA_USER")
    grafana_password = os.environ.get("GRAFANA_PASSWORD")

    missing = [
        name for name, value in [
            ("ACEX_API_URL", api_url),
            ("GRAFANA_URL", grafana_url),
        ] if not value
    ]
    if missing:
        logger.error(f"Missing required env vars: {', '.join(missing)}")
        sys.exit(1)

    has_token = bool(grafana_token)
    has_basic = bool(grafana_user and grafana_password)
    if has_token == has_basic:
        logger.error(
            "Set either GRAFANA_TOKEN or GRAFANA_USER+GRAFANA_PASSWORD (not both, not neither)"
        )
        sys.exit(1)

    acex_verify_ssl = _bool_env("ACEX_VERIFY_SSL", False)
    grafana_verify_ssl = _bool_env("GRAFANA_VERIFY_SSL", True)
    folder_uid = os.environ.get("GRAFANA_FOLDER_UID", "acex")
    folder_title = os.environ.get("GRAFANA_FOLDER_TITLE", "ACEX")
    poll_interval = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))
    prune_dashboards = _bool_env("PRUNE_DASHBOARDS", True)

    client = Acex(baseurl=f"{api_url.rstrip('/')}/", verify=acex_verify_ssl)
    grafana = GrafanaClient(
        url=grafana_url,
        token=grafana_token if has_token else None,
        basic_auth=(grafana_user, grafana_password) if has_basic else None,
        verify_ssl=grafana_verify_ssl,
    )

    agent = GrafanaAgent(
        client=client,
        grafana=grafana,
        folder_uid=folder_uid,
        folder_title=folder_title,
        poll_interval=poll_interval,
        prune_dashboards=prune_dashboards,
    )

    agent.run()


if __name__ == "__main__":
    main()
