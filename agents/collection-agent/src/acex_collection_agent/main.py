"""Collection Agent entrypoint — poll manifest, collect data, upload results."""

import os
import sys
import time
import logging

from acex_collection_agent.agent import CollectionAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("paramiko").setLevel(logging.WARNING)
logging.getLogger("scrapli").setLevel(logging.WARNING)
logging.getLogger("scrapli.transport").setLevel(logging.CRITICAL + 10)  # suppress contextless "timed out"/"auth failed" messages
logging.getLogger("scrapli.channel").setLevel(logging.CRITICAL + 10)
logging.getLogger("asyncssh").setLevel(logging.WARNING)
logger = logging.getLogger("acex_collection_agent")


def main():
    api_url = os.environ.get("ACEX_API_URL")
    agent_id = os.environ.get("COLLECTION_AGENT_ID")

    if not api_url or not agent_id:
        logger.error("ACEX_API_URL and COLLECTION_AGENT_ID environment variables are required")
        sys.exit(1)

    agent_id = int(agent_id)
    verify_ssl = os.environ.get("ACEX_VERIFY_SSL", "false").lower() == "true"
    _max_concurrent_raw = int(os.environ.get("COLLECTION_MAX_CONCURRENT", "20"))
    if _max_concurrent_raw > 250:
        logger.warning(f"COLLECTION_MAX_CONCURRENT={_max_concurrent_raw} exceeds maximum of 250, clamping to 250")
    max_concurrent = min(_max_concurrent_raw, 250)

    agent = CollectionAgent(
        api_url=api_url,
        agent_id=agent_id,
        verify_ssl=verify_ssl,
        max_concurrent=max_concurrent,
    )

    agent.run()


if __name__ == "__main__":
    main()
