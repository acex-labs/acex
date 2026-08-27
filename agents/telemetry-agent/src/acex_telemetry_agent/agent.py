"""Polls observability agent manifest, writes telegraf.conf when revision changes, acks."""

import logging
import os
import time

from acex_client import Acex
from acex_devkit.models.telemetry_agent import TelemetryAgentAck

logger = logging.getLogger("acex_telemetry_agent")


class TelemetryAgent:
    def __init__(
        self,
        client: Acex,
        agent_id: int,
        config_path: str,
        poll_interval: int = 60,
    ):
        self.client = client
        self.agent_id = agent_id
        self.config_path = config_path
        self.poll_interval = poll_interval
        self._last_revision = None

    def run(self):
        logger.info(f"Telemetry Agent started (agent_id={self.agent_id}, config_path={self.config_path})")

        while True:
            try:
                agent = self._fetch_agent()
                if agent is None:
                    time.sleep(self.poll_interval)
                    continue

                revision = agent.config_revision

                first_run = self._last_revision is None and not os.path.exists(self.config_path)
                revision_changed = self._last_revision is not None and revision != self._last_revision

                if first_run or revision_changed:
                    if revision_changed:
                        logger.info(f"Config revision changed ({self._last_revision} -> {revision})")
                    self._update_config()

                self._ack(revision)
                self._last_revision = revision

                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("Shutting down")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                time.sleep(self.poll_interval)

    def _fetch_agent(self):
        try:
            return self.client.observability.agents.get(self.agent_id)
        except Exception as e:
            logger.error(f"Failed to fetch agent: {e}")
            return None

    def _update_config(self) -> bool:
        try:
            # Real secrets are required here — this file is what telegraf actually runs.
            content = self.client.observability.agents.config(id=self.agent_id, reveal_secrets=True)

            os.makedirs(os.path.dirname(self.config_path) or ".", exist_ok=True)
            tmp_path = f"{self.config_path}.tmp"
            with open(tmp_path, "w") as f:
                f.write(content)
            os.replace(tmp_path, self.config_path)

            logger.info(f"Wrote telegraf config to {self.config_path} ({len(content)} bytes)")
            return True
        except Exception as e:
            logger.error(f"Failed to update config: {e}")
            return False

    def _ack(self, config_revision: int):
        try:
            self.client.observability.agents.ack(
                id=self.agent_id,
                payload=TelemetryAgentAck(config_revision=config_revision),
            )
        except Exception as e:
            logger.warning(f"Failed to ack revision {config_revision}: {e}")
