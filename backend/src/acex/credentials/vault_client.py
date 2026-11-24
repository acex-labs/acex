"""Thin wrapper around HashiCorp Vault (hvac)."""

import logging
import threading

logger = logging.getLogger("acex.vault")


class VaultClient:
    """Reads secrets from Vault KV v2.

    A client that logged in with an AppRole logs in again when its token has stopped working, so it keeps reading
    after the token has expired. A client given a token has nothing to log in with and behaves as it always did.
    """

    def __init__(self, url: str, token: str = None, role_id: str = None, secret_id: str = None, verify: bool = True):
        try:
            import hvac
        except ImportError as exc:
            raise RuntimeError(
                "HashiCorp Vault support requires the 'hvac' package. Install it with: pip install hvac"
            ) from exc

        self._hvac = hvac
        self._client = hvac.Client(url=url, token=token, verify=verify)
        self._role_id = role_id
        self._secret_id = secret_id
        # Readers run on several threads. The count of logins tells a reader whose read failed whether another
        # reader has logged in again since, so the readers of an expired token make one login between them.
        self._login_lock = threading.Lock()
        self._logins = 0

        # AppRole auth (preferred for production)
        if role_id and secret_id:
            self._log_in()
            logger.info("Authenticated to Vault via AppRole")
        elif token:
            logger.info("Authenticated to Vault via token")
        else:
            raise RuntimeError("Vault requires either token or role_id+secret_id for authentication")

        if not self._client.is_authenticated():
            raise RuntimeError("Vault authentication failed")

    def _log_in(self) -> None:
        resp = self._client.auth.approle.login(role_id=self._role_id, secret_id=self._secret_id)
        self._client.token = resp["auth"]["client_token"]
        self._logins += 1

    def _logged_in_again(self, logins_before_the_read: int) -> bool:
        """After a read was refused (403): log in again, unless that would not help. True means the read may be tried
        once more.

        A 403 also means that the policy of a working token does not allow the path, and then another login changes
        nothing, so the token is asked whether it still works before anything else is done.
        """
        if not (self._role_id and self._secret_id):
            return False
        with self._login_lock:
            if self._logins != logins_before_the_read:
                return True  # another reader has logged in since this read started
            if self._client.is_authenticated():
                return False
            logger.warning("The Vault token no longer works, logging in again via AppRole")
            self._log_in()
            return True

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

        logins_before = self._logins
        try:
            try:
                return self._read(mount_point, secret_path)
            except self._hvac.exceptions.Forbidden:
                if not self._logged_in_again(logins_before):
                    raise
                return self._read(mount_point, secret_path)
        except Exception as e:
            raise RuntimeError(f"Failed to read Vault secret at '{path}': {e}") from e

    def _read(self, mount_point: str, secret_path: str) -> dict:
        response = self._client.secrets.kv.v2.read_secret_version(path=secret_path, mount_point=mount_point)
        return response["data"]["data"]
