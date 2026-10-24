"""Collector — uses NEDs to fetch running-configs and uploads to ACEX."""

import asyncio
import logging

from acex_client import Acex
from acex_client.exceptions import AcexHTTPError
from acex_devkit.drivers import Session
from acex_devkit.exceptions import AuthenticationFailed, ConnectionTimeout
from acex_devkit.models.agent_manifest import ManifestTarget
from acex_devkit.models.config_snapshot import DeviceConfigUpload
from acex_devkit.models.credential import CredentialSecret
from acex_devkit.models.lldp_neighbor import LldpNeighborEntry, LldpNeighborUpload

logger = logging.getLogger("acex_collection_agent")

# What the CLI transports log in with. A node's other credentials (SNMP communities and the like)
# are not this agent's to fetch.
CREDENTIAL_TYPES = ("userpass", "privilege_escalation")


class Collector:
    def __init__(self, client: Acex):
        self.client = client

    async def collect_all(self, targets: list[ManifestTarget], max_concurrent: int = 20) -> list[dict]:
        """Collect configs from all targets concurrently, bounded by max_concurrent."""
        sem = asyncio.Semaphore(max_concurrent)

        async def bounded(target):
            async with sem:
                return await self._collect_one(target)

        return list(await asyncio.gather(*[bounded(t) for t in targets]))

    def _fetch_credential_secret(self, credential_id: int) -> CredentialSecret | None:
        """Fetch decrypted credential fields from ACEX API."""
        try:
            return self.client.inventory.credentials.secret(id=credential_id)
        except Exception as e:
            logger.warning(f"Failed to fetch credentials {credential_id}: {e}")
        return None

    async def _collect_one(self, target: ManifestTarget) -> dict:
        """Collect config and neighbors from a single target through a session of its NED driver."""
        node_id = target.node_id
        hostname = target.hostname or f"node-{node_id}"
        target_ip = target.target_ip
        ned_id = target.ned_id

        def err(message: str) -> dict:
            return {
                "node_id": node_id,
                "hostname": hostname,
                "status": "error",
                "message": message,
            }

        if not target_ip:
            return err("No management IP")
        if not ned_id:
            return err("No NED configured")

        credentials = []
        for credential_type in CREDENTIAL_TYPES:
            credential_id = target.credentials.get(credential_type)
            if credential_id is None:
                continue
            secret = await asyncio.to_thread(self._fetch_credential_secret, credential_id)
            if secret is not None:
                credentials.append(secret)
            elif credential_type == "userpass":
                return err("Failed to fetch credentials")
            else:
                logger.warning(f"Failed to fetch {credential_type} credential for node {node_id}")

        driver = self.client.neds.get_driver_instance(ned_id)
        if driver is None:
            return err(f"NED '{ned_id}' not loaded")

        logger.info(f"Collecting config from {hostname} ({target_ip}) via {ned_id}")
        try:
            async with driver.connect(target_ip, credentials) as session:
                running_config = await session.get_config()
                if not running_config:
                    return err("Empty config returned")

                config_result = await asyncio.to_thread(self._upload_config, node_id, hostname, running_config)
                await self._collect_neighbors(session, node_id, hostname)
            return config_result
        except AuthenticationFailed:
            logger.warning(f"  {hostname} ({target_ip}): Authentication failed")
            return err("Authentication failed")
        except ConnectionTimeout:
            logger.warning(f"  {hostname} ({target_ip}): Connection timed out")
            return err("Connection timed out")
        except Exception as e:
            logger.warning(f"  {hostname} ({target_ip}): {e}")
            return err(str(e))

    async def _collect_neighbors(self, session: Session, node_id: int, hostname: str) -> None:
        """Upload LLDP/CDP neighbors when the driver reads them. Never fails the collection."""
        if session.state is None or "get_lldp_neighbors" not in session.state.implemented():
            return
        try:
            neighbors = await session.get_lldp_neighbors()
            if neighbors:
                await asyncio.to_thread(self._upload_neighbors, node_id, neighbors)
                logger.info(f"  {hostname}: {len(neighbors)} neighbors uploaded")
        except Exception as e:
            logger.warning(f"  {hostname}: neighbor collection failed: {e}")

    def _upload_config(self, node_id: int, hostname: str, config_content: str) -> dict:
        """Upload collected config to ACEX observed-configuration API."""
        try:
            self.client.inventory.node_instances.upload_observed(
                str(node_id),
                payload=DeviceConfigUpload(content=config_content),
            )
        except AcexHTTPError as e:
            if e.status_code == 409:
                return {
                    "node_id": node_id,
                    "hostname": hostname,
                    "status": "unchanged",
                    "message": "Config not changed",
                }
            return {
                "node_id": node_id,
                "hostname": hostname,
                "status": "error",
                "message": f"Upload failed ({e.status_code})",
            }
        except Exception as e:
            return {
                "node_id": node_id,
                "hostname": hostname,
                "status": "error",
                "message": f"Upload failed: {e}",
            }
        return {
            "node_id": node_id,
            "hostname": hostname,
            "status": "ok",
            "message": "Config uploaded",
        }

    def _upload_neighbors(self, node_id: int, neighbors: list[LldpNeighborEntry]):
        """Upload LLDP/CDP neighbors to ACEX API."""
        try:
            self.client.operations.lldp.upload(
                payload=LldpNeighborUpload(node_instance_id=node_id, neighbors=neighbors),
            )
        except AcexHTTPError as e:
            if e.status_code not in (200, 409):
                logger.warning(f"  Node #{node_id}: neighbor upload failed ({e.status_code})")
        except Exception as e:
            logger.warning(f"  Node #{node_id}: neighbor upload failed: {e}")
