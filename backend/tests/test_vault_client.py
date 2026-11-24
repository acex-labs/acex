"""The Vault client keeps reading after its token has expired, when it has an AppRole to log in again with.

hvac is replaced by a small stand-in for Vault: a token is valid until the test expires it, a login hands out a new
one, and a read is refused (403) when the token is not valid or the policy does not allow the path.
"""

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

    def issue(self) -> str:
        token = f"token-{self.logins}"
        self.valid.add(token)
        return token

    def expire_every_token(self):
        self.valid.clear()


class FakeClient:
    def __init__(self, vault: FakeVault, url, token, verify):
        self.vault, self.token, self.url, self.verify = vault, token, url, verify
        self.auth = SimpleNamespace(approle=SimpleNamespace(login=self._approle_login))
        self.secrets = SimpleNamespace(kv=SimpleNamespace(v2=SimpleNamespace(read_secret_version=self._read)))
        if token in vault.statics:
            vault.valid.add(token)

    def _approle_login(self, role_id, secret_id):
        time.sleep(self.vault.login_seconds)
        if self.vault.login_error:
            raise self.vault.login_error
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


def test_a_client_without_a_token_or_an_approle_does_not_start(vault):
    with pytest.raises(RuntimeError, match="token or role_id"):
        VaultClient("https://vault.example.com")


def test_a_path_without_a_mount_is_refused(vault):
    with pytest.raises(ValueError, match="Invalid vault path"):
        app_role_client().read_secret("secret")


def test_the_data_prefix_of_a_full_path_is_accepted(vault):
    assert app_role_client().read_secret("secret/data/network/core")["password"] == "pw"
