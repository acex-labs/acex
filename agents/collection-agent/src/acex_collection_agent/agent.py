"""Core agent loop — polls manifest frequently, runs collection on interval."""

import time
import logging

import requests
from acex_client.acex.acex import Acex

from acex_collection_agent.collector import Collector

logger = logging.getLogger("acex_collection_agent")

POLL_INTERVAL = 60  # Poll manifest every 60s for liveness + change detection


class CollectionAgent:

    def __init__(self, api_url: str, agent_id: int, verify_ssl: bool = False):
        self.agent_id = agent_id
        self.client = Acex(baseurl=api_url, verify=verify_ssl)
        self.collector = Collector(self.client)
        self._last_revision = None
        self._last_collection = 0

    def run(self):
        """Main loop — poll manifest every 60s, collect on interval or revision change."""
        logger.info(f"Collection Agent started (agent_id={self.agent_id})")

        while True:
            try:
                manifest = self._fetch_manifest()
                if manifest is None:
                    logger.warning("Failed to fetch manifest, retrying in 60s")
                    time.sleep(POLL_INTERVAL)
                    continue

                interval = manifest.get("interval_seconds", 21600)
                revision = manifest.get("config_revision", 0)
                now = time.time()

                revision_changed = self._last_revision is not None and revision != self._last_revision
                interval_elapsed = (now - self._last_collection) >= interval

                should_collect = revision_changed or interval_elapsed or self._last_collection == 0

                if should_collect:
                    if revision_changed:
                        logger.info(f"Config revision changed ({self._last_revision} -> {revision})")
                    self._ensure_neds(manifest)
                    self._collect(manifest)
                    self._last_collection = now

                self._last_revision = revision
                time.sleep(POLL_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Shutting down")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                time.sleep(POLL_INTERVAL)

    def _fetch_manifest(self) -> dict | None:
        """Fetch manifest from ACEX API."""
        try:
            url = f"/inventory/collection_agents/{self.agent_id}/manifest"
            full_url = f"{self.client.rest.url}{url}"
            response = requests.get(full_url, verify=self.client.rest.verify)
            if response.status_code != 200:
                logger.warning(f"Manifest request failed: {response.status_code} {full_url}")
                return None
            data = response.json()
            if not data:
                return None

            targets = data.get("targets", [])
            revision = data.get("config_revision", 0)
            logger.debug(
                f"Manifest polled: rev={revision}, "
                f"{len(targets)} targets"
            )
            self._ack_manifest(revision)
            return data
        except Exception as e:
            logger.error(f"Failed to fetch manifest: {e}")
            return None

    def _ack_manifest(self, config_revision: int):
        """Acknowledge receipt of manifest revision to ACEX API."""
        try:
            url = f"{self.client.rest.url}/inventory/collection_agents/{self.agent_id}/ack"
            requests.post(url, json={"config_revision": config_revision}, verify=self.client.rest.verify)
        except Exception as e:
            logger.warning(f"Failed to ack manifest: {e}")

    def _ensure_neds(self, manifest: dict):
        """Install any missing NEDs required by targets."""
        required_neds = {t["ned_id"] for t in manifest.get("targets", []) if t.get("ned_id")}

        for ned_name in required_neds:
            driver = self.client.neds.get_driver(ned_name)
            if driver is None:
                missing = self.client.neds.get_missing()
                for ned in missing:
                    if ned.name == ned_name:
                        logger.info(f"Installing NED: {ned.name} ({ned.package_name})")
                        self.client.neds.install(ned)
                        break
                else:
                    logger.warning(f"NED '{ned_name}' not found on API")

    def _collect(self, manifest: dict):
        """Run config collection for all targets."""
        targets = manifest.get("targets", [])
        if not targets:
            logger.info("No targets in manifest, nothing to collect")
            return

        results = self.collector.collect_all(targets)

        succeeded = sum(1 for r in results if r["status"] == "ok")
        unchanged = sum(1 for r in results if r["status"] == "unchanged")
        failed = sum(1 for r in results if r["status"] == "error")

        logger.info(
            f"Collection complete: {succeeded} collected, "
            f"{unchanged} unchanged, {failed} failed"
        )

        for r in results:
            if r["status"] == "error":
                logger.warning(f"  Node #{r['node_id']}: {r['message']}")
