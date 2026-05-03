"""Telemetry Agent entrypoint — polls config manifest, writes telegraf.conf."""

import os
import sys
import logging

from acex_client.acex.acex import Acex

from acex_telemetry_agent.agent import TelemetryAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("acex_telemetry_agent")


def main():
    api_url = os.environ.get("ACEX_API_URL")
    agent_id = os.environ.get("TELEMETRY_AGENT_ID")

    if not api_url or not agent_id:
        logger.error("ACEX_API_URL and TELEMETRY_AGENT_ID environment variables are required")
        sys.exit(1)

    agent_id = int(agent_id)
    verify_ssl = os.environ.get("ACEX_VERIFY_SSL", "false").lower() == "true"
    config_path = os.environ.get("TELEGRAF_CONFIG_PATH", "/etc/telegraf/telegraf.conf")
    poll_interval = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))

    client = Acex(baseurl=api_url, verify=verify_ssl)

    agent = TelemetryAgent(
        client=client,
        agent_id=agent_id,
        config_path=config_path,
        poll_interval=poll_interval,
    )

    agent.run()


if __name__ == "__main__":
    main()
