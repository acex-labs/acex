"""Collector — uses NEDs to fetch running-configs and uploads to ACEX."""

import asyncio
import logging
import base64

import requests
from acex_client.acex.acex import Acex
from acex_devkit.models.node_response import NodeListItem
from acex_devkit.models.management_connection import ManagementConnection

logger = logging.getLogger("acex_collection_agent")


class Collector:

    def __init__(self, client: Acex):
        self.client = client

    async def collect_all(self, targets: list[dict]) -> list[dict]:
        """Collect configs from all targets concurrently."""
        tasks = [self._collect_one(target) for target in targets]
        return list(await asyncio.gather(*tasks))

    def _fetch_credential_secret(self, credential_id: int) -> dict | None:
        """Fetch decrypted credential fields from ACEX API."""
        try:
            url = f"{self.client.rest.url}/inventory/credentials/{credential_id}/secret"
            response = requests.get(url, verify=self.client.rest.verify)
            if response.ok:
                return response.json()
            logger.warning(f"Failed to fetch credentials {credential_id}: {response.status_code}")
        except Exception as e:
            logger.warning(f"Failed to fetch credentials {credential_id}: {e}")
        return None

    async def _collect_one(self, target: dict) -> dict:
        """Collect config from a single target, dispatching to async or sync driver path."""
        node_id = target["node_id"]
        hostname = target.get("hostname", f"node-{node_id}")
        target_ip = target.get("target_ip")
        ned_id = target.get("ned_id")

        def err(message: str) -> dict:
            return {"node_id": node_id, "hostname": hostname, "status": "error", "message": message}

        if not target_ip:
            return err("No management IP")
        if not ned_id:
            return err("No NED configured")

        credentials = target.get("credentials", {})
        creds = {}
        userpass_id = credentials.get("userpass")
        if userpass_id:
            secret = await asyncio.to_thread(self._fetch_credential_secret, userpass_id)
            if secret:
                creds = secret.get("fields", {})
            else:
                return err("Failed to fetch credentials")

        escalation_id = credentials.get("privilege_escalation")
        if escalation_id:
            secret = await asyncio.to_thread(self._fetch_credential_secret, escalation_id)
            if secret:
                creds["enable_password"] = secret.get("fields", {}).get("password", "")
            else:
                logger.warning(f"Failed to fetch privilege_escalation credential for node {node_id}")

        driver = self.client.neds.get_driver_instance(ned_id)
        if driver is None:
            return err(f"NED '{ned_id}' not loaded")

        node = NodeListItem(
            id=node_id,
            asset_ref_id=0,
            logical_node_id=0,
            hostname=hostname,
            vendor=target.get("vendor"),
            os=target.get("os"),
            ned_id=ned_id,
        )
        connection = ManagementConnection(
            node_id=node_id,
            target_ip=target_ip,
            connection_type=target.get("connection_type", "ssh"),
        )

        logger.info(f"Collecting config from {hostname} ({target_ip}) via {ned_id}")
        try:
            if asyncio.iscoroutinefunction(driver.transport.get_config):
                return await self._run_async_driver(driver, node, connection, node_id, hostname, **creds)
            else:
                return await asyncio.to_thread(
                    self._run_sync_driver, driver, node, connection, node_id, hostname, **creds
                )
        except Exception as e:
            return err(str(e))

    async def _run_async_driver(self, driver, node, connection, node_id: int, hostname: str, **creds) -> dict:
        """Transport path for async-native drivers."""
        async with driver.transport.session(connection, **creds):
            running_config = await driver.transport.get_config(node, connection, **creds)
            if not running_config:
                return {"node_id": node_id, "hostname": hostname, "status": "error", "message": "Empty config returned"}

            config_result = await asyncio.to_thread(self._upload_config, node_id, hostname, running_config)

            try:
                neighbors = await driver.transport.get_lldp_neighbors(node, connection, **creds)
                if neighbors:
                    await asyncio.to_thread(self._upload_neighbors, node_id, neighbors)
                    logger.info(f"  {hostname}: {len(neighbors)} neighbors uploaded")
            except NotImplementedError:
                pass
            except Exception as e:
                logger.warning(f"  {hostname}: neighbor collection failed: {e}")

        return config_result

    def _run_sync_driver(self, driver, node, connection, node_id: int, hostname: str, **creds) -> dict:
        """Transport path for synchronous drivers — called via asyncio.to_thread."""
        with driver.transport.session(connection, **creds):
            running_config = driver.transport.get_config(node, connection, **creds)
            if not running_config:
                return {"node_id": node_id, "hostname": hostname, "status": "error", "message": "Empty config returned"}

            config_result = self._upload_config(node_id, hostname, running_config)

            try:
                neighbors = driver.transport.get_lldp_neighbors(node, connection, **creds)
                if neighbors:
                    self._upload_neighbors(node_id, neighbors)
                    logger.info(f"  {hostname}: {len(neighbors)} neighbors uploaded")
            except NotImplementedError:
                pass
            except Exception as e:
                logger.warning(f"  {hostname}: neighbor collection failed: {e}")

        return config_result

    def _upload_config(self, node_id: int, hostname: str, config_content: str) -> dict:
        """Upload collected config to ACEX device_configs API."""
        encoded = base64.b64encode(config_content.encode()).decode()
        url = f"{self.client.rest.url}/operations/device_configs/"

        response = requests.post(
            url,
            json={"node_instance_id": str(node_id), "content": encoded},
            verify=self.client.rest.verify,
        )

        if response.status_code == 409:
            return {"node_id": node_id, "hostname": hostname, "status": "unchanged", "message": "Config not changed"}
        elif response.ok:
            return {"node_id": node_id, "hostname": hostname, "status": "ok", "message": "Config uploaded"}
        else:
            return {"node_id": node_id, "hostname": hostname, "status": "error", "message": f"Upload failed ({response.status_code})"}

    def _upload_neighbors(self, node_id: int, neighbors: list[dict]):
        """Upload LLDP/CDP neighbors to ACEX API."""
        url = f"{self.client.rest.url}/operations/lldp_neighbors/"
        response = requests.post(
            url,
            json={"node_instance_id": node_id, "neighbors": neighbors},
            verify=self.client.rest.verify,
        )
        if response.status_code not in (200, 409):
            logger.warning(f"  Node #{node_id}: neighbor upload failed ({response.status_code})")
