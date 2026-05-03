"""Polls observability agent manifest, writes telegraf.conf when revision changes, acks."""

import os
import time
import logging

import requests
from acex_client.acex.acex import Acex

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
        self.base = f"{client.rest.url}/observability/agents/{agent_id}"
        self._last_revision = None

    def run(self):
        logger.info(
            f"Telemetry Agent started "
            f"(agent_id={self.agent_id}, config_path={self.config_path})"
        )

        while True:
            try:
                manifest = self._fetch_manifest()
                if manifest is None:
                    time.sleep(self.poll_interval)
                    continue

                revision = manifest.get("config_revision", 0)

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

    def _fetch_manifest(self) -> dict | None:
        try:
            response = requests.get(self.base, verify=self.client.rest.verify)
            if response.status_code != 200:
                logger.warning(f"Manifest request failed: {response.status_code} {self.base}")
                return None
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch manifest: {e}")
            return None

    def _update_config(self) -> bool:
        url = f"{self.base}/config"
        try:
            response = requests.get(url, verify=self.client.rest.verify)
            if response.status_code != 200:
                logger.warning(f"Config request failed: {response.status_code} {url}")
                return False
            content = response.text

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
        url = f"{self.base}/ack"
        try:
            requests.post(url, json={"config_revision": config_revision}, verify=self.client.rest.verify)
        except Exception as e:
            logger.warning(f"Failed to ack revision {config_revision}: {e}")
