"""Telemetry Agent entrypoint — polls config manifest, writes telegraf.conf."""

import logging
import os
import sys
import time

from acex_client import Acex

from acex_telemetry_agent.agent import TelemetryAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("acex_telemetry_agent")

NAME_VAR = "TELEMETRY_AGENT_NAME"
ID_VAR = "TELEMETRY_AGENT_ID"  # deprecated in favour of NAME_VAR


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

    verify_ssl = os.environ.get("ACEX_VERIFY_SSL", "true").lower() == "true"
    config_path = os.environ.get("TELEGRAF_CONFIG_PATH", "/etc/telegraf/telegraf.conf")
    poll_interval = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))

    client = Acex(base_url=f"{api_url.rstrip('/')}/", verify=verify_ssl)

    if agent_name:
        agent_id = _resolve_agent_id(client.observability.agents, agent_name, poll_interval)
        if agent_id_env and int(agent_id_env) != agent_id:
            logger.warning(f"{ID_VAR}={agent_id_env} ignored: {NAME_VAR}={agent_name!r} resolves to id {agent_id}")
    else:
        agent_id = int(agent_id_env)
        logger.warning(f"{ID_VAR} is deprecated; set {NAME_VAR} to the agent's name instead")

    agent = TelemetryAgent(
        client=client,
        agent_id=agent_id,
        config_path=config_path,
        poll_interval=poll_interval,
    )

    agent.run()


if __name__ == "__main__":
    main()
