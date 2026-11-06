"""Core agent loop — polls manifest frequently, runs collection on interval."""

import asyncio
import importlib.metadata
import logging
import os
import time

from acex_client import Acex
from acex_devkit.models.agent_manifest import CollectionAgentManifest, ManifestTarget
from acex_devkit.models.collection_agent import CollectionAgentAck

from acex_collection_agent.collector import SUPPORTED_NED_INTERFACES, Collector

logger = logging.getLogger("acex_collection_agent")

POLL_INTERVAL = 60  # Poll manifest every 60s for liveness + change detection

# How soon the nodes that had no driver to collect through are tried again, at most: a driver that was missing or
# refused is fixed from outside, and waiting for the next full collection would leave those nodes unserved for hours.
DRIVER_RETRY_SECONDS = 300


def _build_info() -> tuple[str | None, str | None, str | None]:
    """The version of this package, the commit its image was built from and the branch that build ran on."""
    try:
        version = importlib.metadata.version("acex-collection-agent")
    except importlib.metadata.PackageNotFoundError:
        version = None
    return version, os.environ.get("ACEX_BUILD_ID") or None, os.environ.get("ACEX_BUILD_REF") or None


class CollectionAgent:
    def __init__(self, api_url: str, agent_id: int, verify_ssl: bool = False, max_concurrent: int = 20):
        self.agent_id = agent_id
        self.max_concurrent = max_concurrent
        self.client = Acex(base_url=api_url, verify=verify_ssl, ned_interfaces=SUPPORTED_NED_INTERFACES)
        self.collector = Collector(self.client)
        self._last_revision = None
        self._last_collection = 0
        self._neds_synced = False
        self._waiting_for_driver: set[int] = set()
        self._driver_retry_at = 0.0

    def run(self):
        """Entry point — delegates to async loop."""
        asyncio.run(self._run())

    async def _run(self):
        """Main loop — poll manifest every 60s, collect on interval or revision change."""
        logger.info(f"Collection Agent started (agent_id={self.agent_id}, max_concurrent={self.max_concurrent})")

        while True:
            try:
                manifest = await asyncio.to_thread(self._fetch_manifest)
                if manifest is None:
                    logger.warning("Failed to fetch manifest, retrying in 60s")
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                interval = manifest.interval_seconds
                revision = manifest.config_revision
                now = time.time()

                revision_changed = self._last_revision is not None and revision != self._last_revision
                interval_elapsed = (now - self._last_collection) >= interval

                should_collect = revision_changed or interval_elapsed or self._last_collection == 0
                retry_due = not should_collect and bool(self._waiting_for_driver) and now >= self._driver_retry_at

                if should_collect or retry_due:
                    if revision_changed:
                        logger.info(f"Config revision changed ({self._last_revision} -> {revision})")
                    await asyncio.to_thread(self._ensure_neds)
                    targets = manifest.targets
                    if not should_collect:
                        targets = [t for t in targets if t.node_id in self._waiting_for_driver]
                    results = await self._collect(targets) if targets or should_collect else []
                    if should_collect:
                        self._last_collection = now
                    self._waiting_for_driver = {r["node_id"] for r in results if r.get("driver_unavailable")}
                    self._driver_retry_at = now + DRIVER_RETRY_SECONDS

                self._last_revision = revision
                await asyncio.sleep(POLL_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Shutting down")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                await asyncio.sleep(POLL_INTERVAL)

    def _fetch_manifest(self) -> CollectionAgentManifest | None:
        """Fetch manifest from ACEX API."""
        try:
            manifest = self.client.inventory.collection_agents.manifest(id=self.agent_id)
        except Exception as e:
            logger.error(f"Failed to fetch manifest: {e}")
            return None

        if manifest is None:
            return None

        logger.debug(f"Manifest polled: rev={manifest.config_revision}, {len(manifest.targets)} targets")
        self._ack_manifest(manifest.config_revision)
        return manifest

    def _ack_manifest(self, config_revision: int):
        """Acknowledge receipt of manifest revision to ACEX API."""
        agent_version, build_id, build_ref = _build_info()
        try:
            self.client.inventory.collection_agents.ack(
                id=self.agent_id,
                payload=CollectionAgentAck(
                    config_revision=config_revision, agent_version=agent_version, build_id=build_id, build_ref=build_ref
                ),
            )
        except Exception as e:
            logger.warning(f"Failed to ack manifest: {e}")

    def _ensure_neds(self):
        """Sync local NEDs against the API.

        Installs anything missing or version-mismatched. Runs at startup and
        before every collection cycle, so a NED that is registered or bumped on
        the backend is picked up without restarting the agent. A driver that was
        already imported at an older version is the exception — its code is
        replaced on disk but the running process keeps the module it loaded, so
        that one is only logged.
        """
        try:
            missing = self.client.neds.get_missing()
        except Exception as e:
            logger.warning(f"Failed to query NEDs from API: {e}")
            return

        if not missing:
            if not self._neds_synced:
                not_used = sorted(self.client.neds.incompatible)
                if not_used:
                    logger.info(f"No NED to install; not used by this agent: {', '.join(not_used)}")
                else:
                    logger.info("All NEDs up to date")
                self._neds_synced = True
            return

        for ned in missing:
            logger.info(f"Installing NED {ned.name} ({ned.package_name}) v{ned.version}")
            try:
                usable_now = self.client.neds.install(ned)
            except Exception as e:
                logger.error(f"Failed to install NED {ned.name}: {e}")
                continue

            if not usable_now:
                logger.warning(
                    f"NED {ned.name} v{ned.version} installed, but {ned.package_name} is already "
                    "imported in this process — restart the agent to run the new code"
                )
            elif self.client.neds.get_driver_instance(ned.name) is None:
                reason = self.client.neds.incompatible.get(ned.name) or "its driver class failed to load"
                logger.error(f"NED {ned.name} v{ned.version} installed but not usable: {reason}")
            else:
                logger.info(f"NED {ned.name} v{ned.version} installed and loaded")

        self._neds_synced = True

    async def _collect(self, targets: list[ManifestTarget]) -> list[dict]:
        """Run config collection for the targets and return the result of each."""
        if not targets:
            logger.info("No targets in manifest, nothing to collect")
            return []

        logger.info(f"Starting collection for {len(targets)} nodes")
        t0 = time.time()

        results = await self.collector.collect_all(targets, max_concurrent=self.max_concurrent)

        elapsed = time.time() - t0
        succeeded = sum(1 for r in results if r["status"] == "ok")
        unchanged = sum(1 for r in results if r["status"] == "unchanged")
        errors = [r for r in results if r["status"] == "error"]

        logger.info(
            f"Collection complete in {elapsed:.1f}s: {succeeded} collected, {unchanged} unchanged, {len(errors)} failed"
        )

        if errors:
            from collections import Counter

            counts = Counter(r["message"] for r in errors)
            logger.info("Error summary:")
            for msg, count in counts.most_common():
                logger.info(f"  {count:>4}x  {msg}")

        return results
