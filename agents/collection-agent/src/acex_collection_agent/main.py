"""Collection Agent entrypoint — poll manifest, collect data, upload results."""

import logging
import os
import sys
import time

from acex_client import Acex

from acex_collection_agent.agent import CollectionAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("paramiko").setLevel(logging.WARNING)
logging.getLogger("scrapli").setLevel(logging.WARNING)
logging.getLogger("scrapli.transport").setLevel(logging.CRITICAL + 10)
logging.getLogger("scrapli.channel").setLevel(logging.CRITICAL + 10)
logging.getLogger("asyncssh").setLevel(logging.WARNING)
logger = logging.getLogger("acex_collection_agent")

NAME_VAR = "COLLECTION_AGENT_NAME"
ID_VAR = "COLLECTION_AGENT_ID"  # deprecated in favour of NAME_VAR
LOOKUP_RETRY_SECONDS = 60


def _resolve_agent_id(resource, name: str, retry_seconds: int) -> int:
    """Look up the agent id by exact name, retrying until the API answers.

    The API may not be up yet when the agent starts, and the agent may be
    created after it — so failures are logged and retried rather than fatal.
    """
    while True:
        try:
            agent_id = resource.get_id_by_name(name)
            logger.info(f"Resolved {NAME_VAR}={name!r} to agent id {agent_id}")
            return agent_id
        except LookupError as e:
            logger.error(f"{e}; retrying in {retry_seconds}s")
        except Exception as e:
            logger.warning(f"Could not look up agent {name!r} ({e}); retrying in {retry_seconds}s")
        time.sleep(retry_seconds)


def main():
    api_url = os.environ.get("ACEX_API_URL")
    agent_name = os.environ.get(NAME_VAR) or None
    agent_id_env = os.environ.get(ID_VAR) or None

    if not api_url or not (agent_name or agent_id_env):
        logger.error(f"ACEX_API_URL and {NAME_VAR} (or the deprecated {ID_VAR}) environment variables are required")
        sys.exit(1)

    verify_ssl = os.environ.get("ACEX_VERIFY_SSL", "false").lower() == "true"

    if agent_name:
        lookup_client = Acex(base_url=api_url, verify=verify_ssl)
        agent_id = _resolve_agent_id(lookup_client.inventory.collection_agents, agent_name, LOOKUP_RETRY_SECONDS)
        if agent_id_env and int(agent_id_env) != agent_id:
            logger.warning(f"{ID_VAR}={agent_id_env} ignored: {NAME_VAR}={agent_name!r} resolves to id {agent_id}")
    else:
        agent_id = int(agent_id_env)
        logger.warning(f"{ID_VAR} is deprecated; set {NAME_VAR} to the agent's name instead")
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
