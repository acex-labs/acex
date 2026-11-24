"""Thin wrapper around HashiCorp Vault (hvac)."""

import logging
import threading
from pathlib import Path

logger = logging.getLogger("acex.vault")

#: Where Kubernetes mounts the token of the pod's service account.
SERVICE_ACCOUNT_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
#: The mount a Vault Kubernetes auth method has unless it was enabled under another path.
KUBERNETES_AUTH_MOUNT = "kubernetes"


class VaultClient:
    """Reads secrets from Vault KV v2.

    The client logs in with an AppRole, or from Kubernetes with the token of the pod's service account. If both are
    given the AppRole is used, and either beats a static token. A client that logged in logs in again when its token
    has stopped working, so it keeps reading after the token has expired. A client given a token has nothing to log in
    with and behaves as it always did.

    `verify` is True, False, or the path of a CA file to check Vault's certificate against. It applies to this
    client only, not to any other HTTPS call the process makes.
    """

    def __init__(
        self,
        url: str,
        token: str = None,
        role_id: str = None,
        secret_id: str = None,
        verify: bool | str = True,
        k8s_role: str = None,
        k8s_mount: str = KUBERNETES_AUTH_MOUNT,
        k8s_token_path: str = SERVICE_ACCOUNT_TOKEN_PATH,
    ):
        try:
            import hvac
        except ImportError as exc:
            raise RuntimeError(
                "HashiCorp Vault support requires the 'hvac' package. Install it with: pip install hvac"
            ) from exc

        if isinstance(verify, str) and not Path(verify).is_file():
            raise RuntimeError(f"The CA file for Vault does not exist: {verify}")

        self._hvac = hvac
        self._client = hvac.Client(url=url, token=token, verify=verify)
        self._role_id = role_id
        self._secret_id = secret_id
        self._k8s_role = k8s_role
        self._k8s_mount = k8s_mount
        self._k8s_token_path = k8s_token_path
        self._can_log_in = bool((role_id and secret_id) or k8s_role)
        # Readers run on several threads. The count of logins tells a reader whose read failed whether another
        # reader has logged in again since, so the readers of an expired token make one login between them.
        self._login_lock = threading.Lock()
        self._logins = 0

        # AppRole, then Kubernetes, then a static token
        if role_id and secret_id:
            self._log_in()
            logger.info("Authenticated to Vault via AppRole")
        elif k8s_role:
            self._log_in()
            logger.info("Authenticated to Vault via Kubernetes")
        elif token:
            logger.info("Authenticated to Vault via token")
        else:
            raise RuntimeError("Vault requires a token, role_id+secret_id or a Kubernetes role for authentication")

        if not self._client.is_authenticated():
            raise RuntimeError("Vault authentication failed")

    def _log_in(self) -> None:
        if self._role_id and self._secret_id:
            resp = self._client.auth.approle.login(role_id=self._role_id, secret_id=self._secret_id)
        else:
            # Kubernetes rotates the token of a service account, so the file is read again at every login
            try:
                jwt = Path(self._k8s_token_path).read_text().strip()
            except OSError as e:
                raise RuntimeError(f"Cannot read the service account token at {self._k8s_token_path}: {e}") from e
            resp = self._client.auth.kubernetes.login(
                role=self._k8s_role, jwt=jwt, use_token=False, mount_point=self._k8s_mount
            )
        self._client.token = resp["auth"]["client_token"]
        self._logins += 1

    def _logged_in_again(self, logins_before_the_read: int) -> bool:
        """After a read was refused (403): log in again, unless that would not help. True means the read may be tried
        once more.

        A 403 also means that the policy of a working token does not allow the path, and then another login changes
        nothing, so the token is asked whether it still works before anything else is done.
        """
        if not self._can_log_in:
            return False
        with self._login_lock:
            if self._logins != logins_before_the_read:
                return True  # another reader has logged in since this read started
            if self._client.is_authenticated():
                return False
            logger.warning("The Vault token no longer works, logging in again")
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
