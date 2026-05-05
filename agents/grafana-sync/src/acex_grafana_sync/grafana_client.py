"""Thin REST client for the Grafana HTTP API."""

import logging

import requests

logger = logging.getLogger("acex_grafana_sync")


class GrafanaClient:

    def __init__(
        self,
        url: str,
        *,
        token: str | None = None,
        basic_auth: tuple[str, str] | None = None,
        verify_ssl: bool = True,
        timeout: int = 30,
    ):
        if (token is None) == (basic_auth is None):
            raise ValueError("Provide exactly one of token or basic_auth")
        self.base = url.rstrip("/")
        self.session = requests.Session()
        if token is not None:
            self.session.headers["Authorization"] = f"Bearer {token}"
        else:
            self.session.auth = basic_auth
        self.session.headers["Content-Type"] = "application/json"
        self.verify = verify_ssl
        self.timeout = timeout

    # --- Folders ---

    def folder_exists(self, uid: str) -> bool:
        r = self.session.get(
            f"{self.base}/api/folders/{uid}", verify=self.verify, timeout=self.timeout
        )
        if r.status_code == 200:
            return True
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return False

    def create_folder(self, uid: str, title: str) -> dict:
        r = self.session.post(
            f"{self.base}/api/folders",
            json={"uid": uid, "title": title},
            verify=self.verify,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def ensure_folder(self, uid: str, title: str) -> None:
        if not self.folder_exists(uid):
            logger.info(f"Creating Grafana folder uid={uid} title={title!r}")
            self.create_folder(uid, title)

    # --- Datasources ---

    def datasource_exists(self, uid: str) -> bool:
        r = self.session.get(
            f"{self.base}/api/datasources/uid/{uid}",
            verify=self.verify,
            timeout=self.timeout,
        )
        if r.status_code == 200:
            return True
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return False

    def create_datasource(self, body: dict) -> dict:
        r = self.session.post(
            f"{self.base}/api/datasources",
            json=body,
            verify=self.verify,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    # --- Dashboards ---

    def dashboard_folder(self, uid: str) -> str | None:
        """Return the folder uid the dashboard lives in, or None if it doesn't exist.

        The top-level "General" folder is reported as the empty string by Grafana.
        Callers that want to restrict writes to a specific folder should treat any
        value other than their target folder uid as a conflict.
        """
        r = self.session.get(
            f"{self.base}/api/dashboards/uid/{uid}",
            verify=self.verify,
            timeout=self.timeout,
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json().get("meta", {}).get("folderUid", "")

    def upsert_dashboard(self, dashboard: dict, folder_uid: str) -> dict:
        body = {
            "dashboard": dashboard,
            "folderUid": folder_uid,
            "overwrite": True,
            "message": "Synced from ACEX backend",
        }
        r = self.session.post(
            f"{self.base}/api/dashboards/db",
            json=body,
            verify=self.verify,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def list_dashboards_in_folder(self, folder_uid: str) -> list[dict]:
        r = self.session.get(
            f"{self.base}/api/search",
            params={"folderUIDs": folder_uid, "type": "dash-db"},
            verify=self.verify,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def delete_dashboard(self, uid: str) -> None:
        r = self.session.delete(
            f"{self.base}/api/dashboards/uid/{uid}",
            verify=self.verify,
            timeout=self.timeout,
        )
        if r.status_code == 404:
            return
        r.raise_for_status()
