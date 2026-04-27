"""Thin wrapper around HashiCorp Vault (hvac)."""

import logging

logger = logging.getLogger("acex.vault")


class VaultClient:

    def __init__(self, url: str, token: str = None, role_id: str = None, secret_id: str = None, verify: bool = True):
        try:
            import hvac
        except ImportError:
            raise RuntimeError(
                "HashiCorp Vault support requires the 'hvac' package. "
                "Install it with: pip install hvac"
            )

        self._client = hvac.Client(url=url, token=token, verify=verify)

        # AppRole auth (preferred for production)
        if role_id and secret_id:
            resp = self._client.auth.approle.login(role_id=role_id, secret_id=secret_id)
            self._client.token = resp["auth"]["client_token"]
            logger.info("Authenticated to Vault via AppRole")
        elif token:
            logger.info("Authenticated to Vault via token")
        else:
            raise RuntimeError("Vault requires either token or role_id+secret_id for authentication")

        if not self._client.is_authenticated():
            raise RuntimeError("Vault authentication failed")

    def read_secret(self, path: str) -> dict:
        """Read a secret from Vault KV v2 and return the data dict.

        Args:
            path: The secret path, e.g. "secret/network/core-switches"

        Returns:
            Dict of key-value pairs, e.g. {"username": "admin", "password": "secret"}
        """
        # Support both "secret/data/..." (full) and "secret/..." (short) paths
        # hvac's read_secret_version expects mount_point and path separately
        parts = path.strip("/").split("/", 1)
        if len(parts) < 2:
            raise ValueError(f"Invalid vault path: {path}. Expected format: mount/path (e.g. secret/network/switches)")

        mount_point = parts[0]
        secret_path = parts[1]

        # Strip "data/" prefix if user included it
        if secret_path.startswith("data/"):
            secret_path = secret_path[5:]

        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                path=secret_path,
                mount_point=mount_point,
            )
            return response["data"]["data"]
        except Exception as e:
            raise RuntimeError(f"Failed to read Vault secret at '{path}': {e}")
