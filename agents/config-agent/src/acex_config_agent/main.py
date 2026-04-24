"""Config Agent entrypoint — poll manifest, collect configs, upload results."""

import os
import sys
import time
import logging

from acex_config_agent.agent import ConfigAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("acex_config_agent")


def main():
    api_url = os.environ.get("ACEX_API_URL")
    agent_id = os.environ.get("CONFIG_AGENT_ID")

    if not api_url or not agent_id:
        logger.error("ACEX_API_URL and CONFIG_AGENT_ID environment variables are required")
        sys.exit(1)

    agent_id = int(agent_id)
    verify_ssl = os.environ.get("ACEX_VERIFY_SSL", "false").lower() == "true"

    agent = ConfigAgent(
        api_url=api_url,
        agent_id=agent_id,
        verify_ssl=verify_ssl,
    )

    agent.run()


if __name__ == "__main__":
    main()
