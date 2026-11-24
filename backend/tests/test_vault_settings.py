"""The Vault settings: a Kubernetes role, where it logs in from, and a CA file for Vault's certificate."""

from types import SimpleNamespace

import pytest
from acex.automation_engine import automationengine
from acex.settings import Settings, VaultSettings


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in (
        "ADDR",
        "TOKEN",
        "ROLE_ID",
        "SECRET_ID",
        "K8S_ROLE",
        "K8S_MOUNT",
        "K8S_TOKEN_PATH",
        "VERIFY",
    ):
        monkeypatch.delenv(f"ACEX_CREDENTIALS_VAULT_{name}", raising=False)


def test_vault_is_off_without_an_address():
    assert not Settings().credentials.vault.configured


@pytest.mark.parametrize(
    "given",
    [
        {"token": "t"},
        {"role_id": "r", "secret_id": "s"},
        {"k8s_role": "acex"},
    ],
    ids=["token", "approle", "kubernetes"],
)
def test_an_address_and_one_way_to_log_in_is_enough(given):
    assert VaultSettings(addr="https://vault.example.com", **given).configured


def test_an_approle_needs_both_its_halves():
    assert not VaultSettings(addr="https://vault.example.com", role_id="r").configured


def test_a_login_without_an_address_is_not_enough():
    assert not VaultSettings(k8s_role="acex").configured


def test_the_kubernetes_settings_are_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("ACEX_CREDENTIALS_VAULT_ADDR", "https://vault.example.com")
    monkeypatch.setenv("ACEX_CREDENTIALS_VAULT_K8S_ROLE", "acex")
    monkeypatch.setenv("ACEX_CREDENTIALS_VAULT_K8S_MOUNT", "k8s-prod")
    monkeypatch.setenv("ACEX_CREDENTIALS_VAULT_K8S_TOKEN_PATH", "/tmp/token")

    vault = Settings().credentials.vault

    assert (vault.k8s_role, vault.k8s_mount, vault.k8s_token_path) == ("acex", "k8s-prod", "/tmp/token")
    assert vault.configured


def test_the_mount_and_the_token_file_have_the_defaults_kubernetes_uses():
    vault = Settings().credentials.vault

    assert vault.k8s_mount == "kubernetes"
    assert vault.k8s_token_path == "/var/run/secrets/kubernetes.io/serviceaccount/token"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("FALSE", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("/etc/vault/ca.pem", "/etc/vault/ca.pem"),
    ],
)
def test_the_certificate_check_is_a_flag_or_the_path_of_a_ca_file(monkeypatch, text, expected):
    monkeypatch.setenv("ACEX_CREDENTIALS_VAULT_VERIFY", text)

    assert Settings().credentials.vault.verify == expected


def test_the_certificate_is_checked_unless_said_otherwise():
    assert Settings().credentials.vault.verify is True


def test_the_engine_gives_the_vault_client_what_the_settings_say(monkeypatch):
    built = {}
    monkeypatch.setattr(automationengine, "VaultClient", lambda **kwargs: built.update(kwargs) or "client")
    monkeypatch.setattr(automationengine, "CredentialManager", lambda db, key, vault_client: vault_client)
    settings = Settings(
        credentials={
            "vault": {
                "addr": "https://vault.example.com",
                "k8s_role": "acex",
                "k8s_mount": "k8s-prod",
                "k8s_token_path": "/tmp/token",
                "verify": "/etc/vault/ca.pem",
            }
        }
    )
    engine = SimpleNamespace(settings=settings, db=None)

    automationengine.AutomationEngine._build_credential_manager(engine)

    assert engine.credential_manager == "client"
    assert built == {
        "url": "https://vault.example.com",
        "token": None,
        "role_id": None,
        "secret_id": None,
        "verify": "/etc/vault/ca.pem",
        "k8s_role": "acex",
        "k8s_mount": "k8s-prod",
        "k8s_token_path": "/tmp/token",
    }
