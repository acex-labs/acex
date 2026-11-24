"""The Vault client keeps reading after its token has expired, when it has an AppRole to log in again with.

hvac is replaced by a small stand-in for Vault: a token is valid until the test expires it, a login hands out a new
one, and a read is refused (403) when the token is not valid or the policy does not allow the path.
"""

import os
import sys
import threading
import time
from types import ModuleType, SimpleNamespace

import pytest
from acex.credentials.vault_client import VaultClient


class Forbidden(Exception):
    pass


class InvalidRequest(Exception):
    pass


class InvalidPath(Exception):
    pass


class VaultDown(Exception):
    pass


class FakeVault:
    """What a Vault server does here: hands out tokens, expires them and answers reads."""

    def __init__(self):
        self.secrets = {"secret/network/core": {"username": "admin", "password": "pw"}}
        self.allowed = set(self.secrets)
        self.valid = set()
        self.logins = 0
        self.login_error = None
        self.login_seconds = 0.0
        self.read_error = None
        self.reads = 0
        self.statics = {"static-token"}
        # Kubernetes auth: what Vault asks the cluster's TokenReview, reduced to the tokens it takes for good
        self.service_account_tokens = set()
        self.kubernetes_logins = []

    def issue(self) -> str:
        token = f"token-{self.logins}"
        self.valid.add(token)
        return token

    def expire_every_token(self):
        self.valid.clear()


class FakeClient:
    def __init__(self, vault: FakeVault, url, token, verify):
        self.vault, self.token, self.url, self.verify = vault, token, url, verify
        self.auth = SimpleNamespace(
            approle=SimpleNamespace(login=self._approle_login),
            kubernetes=SimpleNamespace(login=self._kubernetes_login),
        )
        self.secrets = SimpleNamespace(kv=SimpleNamespace(v2=SimpleNamespace(read_secret_version=self._read)))
        if token in vault.statics:
            vault.valid.add(token)

    def _approle_login(self, role_id, secret_id):
        time.sleep(self.vault.login_seconds)
        if self.vault.login_error:
            raise self.vault.login_error
        self.vault.logins += 1
        return {"auth": {"client_token": self.vault.issue()}}

    def _kubernetes_login(self, role, jwt, use_token=True, mount_point="kubernetes"):
        self.vault.kubernetes_logins.append((role, jwt, mount_point))
        if jwt not in self.vault.service_account_tokens:
            raise InvalidRequest("service account token rejected")
        self.vault.logins += 1
        return {"auth": {"client_token": self.vault.issue()}}

    def is_authenticated(self) -> bool:
        return self.token in self.vault.valid

    def _read(self, path, mount_point):
        self.vault.reads += 1
        if self.vault.read_error:
            raise self.vault.read_error
        if self.token not in self.vault.valid:
            raise Forbidden("permission denied")
        full = f"{mount_point}/{path}"
        if full not in self.vault.allowed:
            raise Forbidden("permission denied")
        if full not in self.vault.secrets:
            raise InvalidPath("no secret there")
        return {"data": {"data": self.vault.secrets[full]}}


@pytest.fixture
def vault(monkeypatch):
    server = FakeVault()
    hvac = ModuleType("hvac")
    hvac.exceptions = SimpleNamespace(
        Forbidden=Forbidden, InvalidRequest=InvalidRequest, InvalidPath=InvalidPath, VaultDown=VaultDown
    )
    hvac.Client = lambda url, token=None, verify=True: FakeClient(server, url, token, verify)
    monkeypatch.setitem(sys.modules, "hvac", hvac)
    return server


def app_role_client() -> VaultClient:
    return VaultClient("https://vault.example.com", role_id="role", secret_id="secret")


def token_client() -> VaultClient:
    return VaultClient("https://vault.example.com", token="static-token")


@pytest.fixture
def pod(tmp_path, vault):
    """A pod whose service account token Vault takes: the path of the file it is mounted in."""
    path = tmp_path / "token"
    path.write_text("jwt-1\n")
    vault.service_account_tokens.add("jwt-1")
    return path


def kubernetes_client(pod, **settings) -> VaultClient:
    return VaultClient("https://vault.example.com", k8s_role="acex", k8s_token_path=str(pod), **settings)


PATH = "secret/network/core"


def test_a_secret_is_read_with_the_token_the_login_gave(vault):
    assert app_role_client().read_secret(PATH) == {"username": "admin", "password": "pw"}
    assert vault.logins == 1


def test_after_the_token_has_expired_the_client_logs_in_again_and_reads(vault):
    client = app_role_client()
    vault.expire_every_token()

    assert client.read_secret(PATH)["username"] == "admin"
    assert vault.logins == 2


def test_the_client_keeps_reading_across_several_expirations(vault):
    client = app_role_client()

    for _ in range(3):
        vault.expire_every_token()
        assert client.read_secret(PATH)["username"] == "admin"

    assert vault.logins == 4


def test_a_working_token_is_not_replaced_when_a_read_is_refused_for_the_policy(vault):
    vault.allowed.discard(PATH)
    client = app_role_client()

    with pytest.raises(RuntimeError, match="permission denied"):
        client.read_secret(PATH)

    assert vault.logins == 1
    assert vault.reads == 1  # nothing was tried again either


def test_the_read_is_tried_once_more_and_no_more_when_the_new_token_is_refused_too(vault):
    client = app_role_client()
    vault.expire_every_token()
    vault.allowed.discard(PATH)

    with pytest.raises(RuntimeError, match="permission denied"):
        client.read_secret(PATH)

    assert vault.logins == 2
    assert vault.reads == 2


@pytest.mark.parametrize("token_expired", [False, True], ids=["token works", "token expired"])
@pytest.mark.parametrize(
    "error",
    [VaultDown("Vault is sealed"), ConnectionError("unreachable"), InvalidPath("no secret there")],
    ids=["sealed", "unreachable", "missing"],
)
def test_other_errors_never_log_in_again(vault, error, token_expired):
    # With an expired token a login is exactly what the client would do for a 403, so this is what tells the two apart
    client = app_role_client()
    if token_expired:
        vault.expire_every_token()
    vault.read_error = error

    with pytest.raises(RuntimeError, match="Failed to read Vault secret"):
        client.read_secret(PATH)

    assert vault.logins == 1
    assert vault.reads == 1


def test_a_login_that_is_refused_is_the_error_of_the_read(vault):
    client = app_role_client()
    vault.expire_every_token()
    vault.login_error = InvalidRequest("invalid secret id")

    with pytest.raises(RuntimeError, match="invalid secret id"):
        client.read_secret(PATH)

    vault.login_error = None
    assert client.read_secret(PATH)["username"] == "admin"  # the next read logs in again


def test_readers_of_an_expired_token_share_one_new_login(vault):
    client = app_role_client()
    vault.expire_every_token()
    vault.login_seconds = 0.05
    readers = 8
    start = threading.Barrier(readers)
    results, errors = [], []

    def read():
        start.wait()
        try:
            results.append(client.read_secret(PATH)["username"])
        except Exception as e:  # noqa: BLE001 - the test reports whatever a reader hit
            errors.append(e)

    threads = [threading.Thread(target=read) for _ in range(readers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert results == ["admin"] * readers
    assert vault.logins == 2  # the first login and one more, not one for each reader


def test_a_client_given_a_token_has_nothing_to_log_in_with_and_behaves_as_before(vault):
    client = token_client()
    assert client.read_secret(PATH)["username"] == "admin"
    vault.expire_every_token()

    with pytest.raises(RuntimeError, match="permission denied"):
        client.read_secret(PATH)

    assert vault.logins == 0
    assert vault.reads == 2


def test_a_client_that_cannot_authenticate_does_not_start(vault):
    vault.login_error = InvalidRequest("invalid secret id")

    with pytest.raises(InvalidRequest):
        app_role_client()


def test_a_client_without_a_way_to_log_in_does_not_start(vault):
    with pytest.raises(RuntimeError, match="Vault requires a token"):
        VaultClient("https://vault.example.com")


def test_a_path_without_a_mount_is_refused(vault):
    with pytest.raises(ValueError, match="Invalid vault path"):
        app_role_client().read_secret("secret")


def test_the_data_prefix_of_a_full_path_is_accepted(vault):
    assert app_role_client().read_secret("secret/data/network/core")["password"] == "pw"


def test_a_pod_logs_in_with_the_token_of_its_service_account(vault, pod):
    client = kubernetes_client(pod)

    assert client.read_secret(PATH)["username"] == "admin"
    assert vault.kubernetes_logins == [("acex", "jwt-1", "kubernetes")]  # the newline of the file is not part of it


def test_the_auth_method_may_be_mounted_elsewhere(vault, pod):
    kubernetes_client(pod, k8s_mount="k8s-prod")

    assert vault.kubernetes_logins == [("acex", "jwt-1", "k8s-prod")]


def test_a_pod_logs_in_again_after_the_token_has_expired(vault, pod):
    client = kubernetes_client(pod)
    vault.expire_every_token()

    assert client.read_secret(PATH)["username"] == "admin"
    assert vault.logins == 2


def test_the_token_file_is_read_again_at_every_login_since_kubernetes_rotates_it(vault, pod):
    client = kubernetes_client(pod)
    vault.service_account_tokens.discard("jwt-1")  # the first token was replaced in the cluster
    vault.service_account_tokens.add("jwt-2")
    pod.write_text("jwt-2\n")
    vault.expire_every_token()

    assert client.read_secret(PATH)["username"] == "admin"
    assert [jwt for _, jwt, _ in vault.kubernetes_logins] == ["jwt-1", "jwt-2"]


def test_an_approle_is_used_before_kubernetes_and_kubernetes_before_a_token(vault, pod):
    both = VaultClient(
        "https://vault.example.com", role_id="role", secret_id="secret", k8s_role="acex", k8s_token_path=str(pod)
    )
    assert vault.kubernetes_logins == []
    assert both.read_secret(PATH)

    kubernetes_and_token = VaultClient(
        "https://vault.example.com", token="static-token", k8s_role="acex", k8s_token_path=str(pod)
    )
    assert len(vault.kubernetes_logins) == 1
    vault.expire_every_token()
    assert kubernetes_and_token.read_secret(PATH)  # it has a login to fall back on, so it is not the static token


def test_a_token_file_that_cannot_be_read_says_so(vault, tmp_path):
    with pytest.raises(RuntimeError, match="Cannot read the service account token"):
        VaultClient("https://vault.example.com", k8s_role="acex", k8s_token_path=str(tmp_path / "missing"))


def test_the_default_token_file_is_the_one_kubernetes_mounts():
    from acex.credentials.vault_client import KUBERNETES_AUTH_MOUNT, SERVICE_ACCOUNT_TOKEN_PATH

    assert SERVICE_ACCOUNT_TOKEN_PATH == "/var/run/secrets/kubernetes.io/serviceaccount/token"
    assert KUBERNETES_AUTH_MOUNT == "kubernetes"


def test_a_service_account_token_vault_refuses_stops_the_start(vault, pod):
    vault.service_account_tokens.clear()

    with pytest.raises(InvalidRequest, match="service account token rejected"):
        kubernetes_client(pod)


def test_a_ca_file_is_given_to_the_vault_client_and_to_nothing_else(vault, tmp_path, monkeypatch):
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    ca = tmp_path / "vault-ca.pem"
    ca.write_text("-----BEGIN CERTIFICATE-----\n-----END CERTIFICATE-----\n")

    client = VaultClient("https://vault.example.com", role_id="role", secret_id="secret", verify=str(ca))

    assert client._client.verify == str(ca)
    assert "REQUESTS_CA_BUNDLE" not in os.environ


def test_a_ca_file_that_does_not_exist_stops_the_start(vault, tmp_path):
    with pytest.raises(RuntimeError, match="CA file for Vault does not exist"):
        VaultClient("https://vault.example.com", role_id="role", secret_id="secret", verify=str(tmp_path / "gone.pem"))


@pytest.mark.parametrize("verify", [True, False])
def test_the_certificate_check_can_still_be_a_flag(vault, verify):
    client = VaultClient("https://vault.example.com", role_id="role", secret_id="secret", verify=verify)

    assert client._client.verify is verify
