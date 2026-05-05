"""Reconciles ACEX-generated Grafana datasources and dashboards into a target Grafana."""

import hashlib
import json
import time
import logging

import requests
from acex_client.acex.acex import Acex

from acex_grafana_sync.grafana_client import GrafanaClient

logger = logging.getLogger("acex_grafana_sync")


class GrafanaAgent:

    def __init__(
        self,
        client: Acex,
        grafana: GrafanaClient,
        folder_uid: str = "acex",
        folder_title: str = "ACEX",
        poll_interval: int = 60,
        prune_dashboards: bool = True,
    ):
        self.client = client
        self.grafana = grafana
        self.folder_uid = folder_uid
        self.folder_title = folder_title
        self.poll_interval = poll_interval
        self.prune_dashboards = prune_dashboards
        self.base = f"{client.rest.url}/observability/grafana"
        self._last_digest: str | None = None
        self._last_apply_succeeded = False

    def run(self):
        logger.info(
            f"Grafana Sync started "
            f"(grafana={self.grafana.base}, folder={self.folder_uid}, "
            f"prune={self.prune_dashboards})"
        )

        while True:
            try:
                self._reconcile_once()
            except KeyboardInterrupt:
                logger.info("Shutting down")
                break
            except Exception as e:
                logger.error(f"Reconcile iteration failed: {e}", exc_info=True)
                self._last_apply_succeeded = False

            try:
                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                logger.info("Shutting down")
                break

    def _reconcile_once(self):
        desired = self._build_desired_state()
        if desired is None:
            return

        digest = self._digest(desired)
        if digest == self._last_digest and self._last_apply_succeeded:
            logger.debug(f"Desired state unchanged (digest={digest[:8]}), skipping reconcile")
            return

        if self._last_digest is None:
            logger.info(f"Initial reconcile (digest={digest[:8]})")
        elif digest != self._last_digest:
            logger.info(
                f"Desired state changed "
                f"({self._last_digest[:8]} -> {digest[:8]}), reconciling"
            )
        else:
            logger.info("Retrying reconcile after previous failure")

        self.grafana.ensure_folder(self.folder_uid, self.folder_title)
        ok = self._apply(desired)

        self._last_digest = digest
        self._last_apply_succeeded = ok

    # --- Desired state ---

    def _build_desired_state(self) -> dict | None:
        ds_listing = self._fetch_json(f"{self.base}/datasources")
        db_listing = self._fetch_json(f"{self.base}/dashboards")
        if ds_listing is None or db_listing is None:
            return None

        datasources = []
        for entry in ds_listing:
            body = self._fetch_json(f"{self.base}/datasources/{entry['uid']}")
            if body is None:
                return None
            datasources.append(body)

        dashboards = []
        for entry in db_listing:
            dashboard = self._fetch_json(f"{self.base}/dashboards/{entry['uid']}")
            if dashboard is None:
                return None
            dashboards.append(dashboard)

        return {"datasources": datasources, "dashboards": dashboards}

    @staticmethod
    def _digest(desired: dict) -> str:
        payload = json.dumps(desired, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()

    # --- Apply ---

    def _apply(self, desired: dict) -> bool:
        ok = True

        for body in desired["datasources"]:
            uid = body["uid"]
            if self.grafana.datasource_exists(uid):
                logger.debug(f"Datasource {uid} already exists, skipping")
                continue
            try:
                self.grafana.create_datasource(body)
                logger.info(f"Created Grafana datasource uid={uid} name={body.get('name')!r}")
            except requests.HTTPError as e:
                ok = False
                logger.error(
                    f"Failed to create datasource {uid}: "
                    f"{e.response.status_code} {e.response.text}"
                )

        applied_uids: set[str] = set()
        for dashboard in desired["dashboards"]:
            uid = dashboard["uid"]
            try:
                existing_folder = self.grafana.dashboard_folder(uid)
            except requests.HTTPError as e:
                ok = False
                logger.error(
                    f"Failed to look up dashboard {uid}: "
                    f"{e.response.status_code} {e.response.text}"
                )
                continue

            if existing_folder is not None and existing_folder != self.folder_uid:
                logger.warning(
                    f"Dashboard uid={uid} lives in folder {existing_folder!r}, "
                    f"refusing to overwrite (we only manage {self.folder_uid!r})"
                )
                continue

            try:
                self.grafana.upsert_dashboard(dashboard, self.folder_uid)
                logger.info(f"Upserted Grafana dashboard uid={uid} title={dashboard.get('title')!r}")
                applied_uids.add(uid)
            except requests.HTTPError as e:
                ok = False
                logger.error(
                    f"Failed to upsert dashboard {uid}: "
                    f"{e.response.status_code} {e.response.text}"
                )

        if self.prune_dashboards:
            desired_uids = {d["uid"] for d in desired["dashboards"]}
            ok = self._prune_dashboards(desired_uids) and ok

        return ok

    def _prune_dashboards(self, desired_uids: set[str]) -> bool:
        try:
            existing = self.grafana.list_dashboards_in_folder(self.folder_uid)
        except requests.HTTPError as e:
            logger.error(
                f"Failed to list dashboards in folder {self.folder_uid}: "
                f"{e.response.status_code} {e.response.text}"
            )
            return False

        ok = True
        for entry in existing:
            uid = entry.get("uid")
            if not uid or uid in desired_uids:
                continue
            try:
                self.grafana.delete_dashboard(uid)
                logger.info(f"Pruned Grafana dashboard uid={uid} (no longer in ACEX)")
            except requests.HTTPError as e:
                ok = False
                logger.error(
                    f"Failed to delete dashboard {uid}: "
                    f"{e.response.status_code} {e.response.text}"
                )
        return ok

    # --- Helpers ---

    def _fetch_json(self, url: str):
        try:
            response = requests.get(url, verify=self.client.rest.verify, timeout=30)
            if response.status_code != 200:
                logger.warning(f"GET {url} failed: {response.status_code} {response.text}")
                return None
            return response.json()
        except Exception as e:
            logger.error(f"GET {url} raised: {e}")
            return None
