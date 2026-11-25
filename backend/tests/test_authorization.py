"""A device login in the clear is for the agents and workers that need it and for admins, not for every valid token.

The check is rolled out in three modes: off (nothing is checked), log (what would be refused is logged) and enforce
(refused with 403). The roles are read from the token as the settings say.
"""

import logging

import pytest
from acex.api import auth
from acex.api.routers import credentials
from acex.settings import AuthorizationSettings, Settings
from acex_devkit.models.credential import CredentialSecret
from fastapi import FastAPI
from fastapi.testclient import TestClient

ISSUER = "https://keycloak.example/realms/acex"
ROLE_NAMES = {"admin": "acex-admin", "service": "acex-service"}
KEYCLOAK_CLAIMS = ("realm_access.roles", "resource_access.{audience}.roles")
SECRET = "/api/v1/inventory/credentials/7/secret"


class FakeCredentialManager:
    def get_secret(self, id: int) -> CredentialSecret:
        return CredentialSecret(id=id, credential_type="userpass", fields={"username": "u", "password": "p"})

    def query(self, name: str | None = None) -> list:
        return []

    def __getattr__(self, name):
        # The router registers every credential route; the ones this test does not call only need to exist.
        return lambda: None


class FakeEngine:
    credential_manager = FakeCredentialManager()


@pytest.fixture(autouse=True)
def _reset_auth():
    yield
    auth.configure(None)
    auth.configure_authorization("off", KEYCLOAK_CLAIMS, ROLE_NAMES)


def _client(mode: str, claims: dict, issuer: str | None = ISSUER, roles_claims=KEYCLOAK_CLAIMS) -> TestClient:
    auth.configure(issuer, "acex")
    auth.configure_authorization(mode, roles_claims, ROLE_NAMES)
    app = FastAPI()
    app.include_router(credentials.create_router(FakeEngine()))
    app.dependency_overrides[auth.get_current_user] = lambda: claims
    return TestClient(app)


NO_ROLES = {"sub": "alice", "aud": "acex"}
ADMIN = {"sub": "alice", "realm_access": {"roles": ["acex-admin"]}}
SERVICE = {"sub": "svc", "azp": "collection-agent", "realm_access": {"roles": ["offline_access", "acex-service"]}}
CLIENT_ROLE = {"sub": "svc", "resource_access": {"acex": {"roles": ["acex-service"]}}}
OTHER_ROLE = {"sub": "bob", "realm_access": {"roles": ["acex-viewer"]}}
OTHER_CLIENTS_ROLE = {"sub": "bob", "resource_access": {"other-client": {"roles": ["acex-admin"]}}}


class TestRolesOfAToken:
    @pytest.fixture(autouse=True)
    def _keycloak(self):
        auth.configure(ISSUER, "acex")
        auth.configure_authorization("enforce", KEYCLOAK_CLAIMS, ROLE_NAMES)

    def should_read_the_realm_roles(self):
        assert auth.roles_of(ADMIN) == {"acex-admin"}

    def should_read_the_client_roles_of_the_audience(self):
        assert auth.roles_of(CLIENT_ROLE) == {"acex-service"}

    def should_not_read_the_roles_of_another_client(self):
        assert auth.roles_of(OTHER_CLIENTS_ROLE) == set()

    def should_read_both_places_at_once(self):
        claims = {"realm_access": {"roles": ["a"]}, "resource_access": {"acex": {"roles": ["b"]}}}
        assert auth.roles_of(claims) == {"a", "b"}

    def should_read_a_path_of_the_settings(self):
        auth.configure_authorization("enforce", ("roles",), ROLE_NAMES)
        assert auth.roles_of({"roles": ["acex-admin", "x"]}) == {"acex-admin", "x"}

    def should_read_a_claim_of_names_in_one_string(self):
        auth.configure_authorization("enforce", ("groups",), ROLE_NAMES)
        assert auth.roles_of({"groups": "acex-admin acex-service"}) == {"acex-admin", "acex-service"}

    @pytest.mark.parametrize(
        "claims",
        [
            {},
            {"realm_access": None},
            {"realm_access": "acex-admin"},
            {"realm_access": {"roles": 7}},
            {"realm_access": {"roles": [1, None]}},
        ],
    )
    def should_skip_what_is_not_a_list_of_names(self, claims):
        assert auth.roles_of(claims) == set()


class TestOff:
    @pytest.mark.parametrize("claims", [NO_ROLES, ADMIN, OTHER_ROLE])
    def should_let_every_token_through_as_before(self, claims):
        assert _client("off", claims).get(SECRET).status_code == 200


class TestEnforce:
    @pytest.mark.parametrize("claims", [ADMIN, SERVICE, CLIENT_ROLE])
    def should_give_the_secret_to_the_admin_and_the_service_roles(self, claims):
        response = _client("enforce", claims).get(SECRET)
        assert response.status_code == 200
        assert response.json()["fields"] == {"username": "u", "password": "p"}

    @pytest.mark.parametrize("claims", [NO_ROLES, OTHER_ROLE, OTHER_CLIENTS_ROLE])
    def should_refuse_a_valid_token_without_the_role(self, claims):
        response = _client("enforce", claims).get(SECRET)
        assert response.status_code == 403
        assert "acex-admin" in response.json()["detail"] and "acex-service" in response.json()["detail"]
        assert "password" not in response.text

    def should_leave_the_other_credential_routes_as_they_are(self):
        assert _client("enforce", NO_ROLES).get("/api/v1/inventory/credentials").status_code == 200

    def should_use_the_role_names_of_the_settings(self):
        auth.configure(ISSUER, "acex")
        auth.configure_authorization("enforce", ("roles",), {"admin": "netops", "service": "robots"})
        app = FastAPI()
        app.include_router(credentials.create_router(FakeEngine()))
        claims = {"sub": "x", "roles": ["robots"]}
        app.dependency_overrides[auth.get_current_user] = lambda: claims
        assert TestClient(app).get(SECRET).status_code == 200
        claims["roles"] = ["acex-admin"]
        assert TestClient(app).get(SECRET).status_code == 403

    def should_not_check_roles_when_there_is_no_issuer(self):
        # Dev mode: nobody has a token, so nobody has roles.
        assert _client("enforce", {}, issuer=None).get(SECRET).status_code == 200

    def should_log_the_refusal(self, caplog):
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            _client("enforce", SERVICE | {"realm_access": {"roles": []}}).get(SECRET)
        assert "denied" in caplog.text and "collection-agent" in caplog.text


class TestLog:
    def should_let_a_token_without_the_role_through(self):
        assert _client("log", NO_ROLES).get(SECRET).status_code == 200

    def should_say_what_enforce_would_have_refused(self, caplog):
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            _client("log", NO_ROLES).get(SECRET)
        assert "Would be refused" in caplog.text and "alice" in caplog.text
        assert "/credentials/{id}/secret" in caplog.text

    def should_say_it_once_for_a_caller_that_asks_again_and_again(self, caplog):
        client = _client("log", NO_ROLES)
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            for _ in range(5):
                client.get(SECRET)
        assert caplog.text.count("Would be refused") == 1

    def should_say_nothing_about_a_token_with_the_role(self, caplog):
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            _client("log", ADMIN).get(SECRET)
        assert caplog.text == ""


class TestSettings:
    def should_be_off_unless_asked(self):
        assert AuthorizationSettings().mode == "off"

    def should_read_the_environment(self, monkeypatch):
        monkeypatch.setenv("ACEX_AUTHZ_MODE", "enforce")
        monkeypatch.setenv("ACEX_AUTHZ_ROLES_CLAIMS", "groups, realm_access.roles")
        monkeypatch.setenv("ACEX_AUTHZ_ADMIN_ROLE", "netops")
        settings = Settings().authz
        assert (settings.mode, settings.roles_claims, settings.admin_role) == (
            "enforce",
            ["groups", "realm_access.roles"],
            "netops",
        )

    def should_refuse_a_mode_it_does_not_know(self):
        with pytest.raises(ValueError):
            AuthorizationSettings(mode="strict")


class TestThroughTheApp:
    """The whole chain: settings, a signed token, the roles in it and a credential created through the API."""

    @pytest.fixture
    def tokens(self, tmp_path, monkeypatch):
        from acex.automation_engine.automationengine import AutomationEngine
        from acex.database import Connection
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from jose import jwk, jwt

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ACEX_CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        ).decode()
        public = jwk.RSAKey(
            key.public_key()
            .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
            .decode(),
            "RS256",
        ).to_dict()
        public["kid"] = "test"
        monkeypatch.setattr(auth, "_get_jwks", lambda force_refresh=False: {"keys": [public]})

        def token(**claims):
            body = {"iss": ISSUER, "aud": "acex", "sub": "someone", **claims}
            return jwt.encode(body, pem, algorithm="RS256", headers={"kid": "test"})

        settings = Settings(oidc={"issuer_url": ISSUER}, authz={"mode": "enforce"})
        engine = AutomationEngine(db_connection=Connection(), settings=settings)
        client = TestClient(engine.create_app())
        yield client, token
        auth.set_dev_mode(False)

    def should_give_the_secret_only_to_a_token_with_a_role(self, tokens):
        client, token = tokens
        plain = {"Authorization": f"Bearer {token()}"}
        created = client.post(
            "/api/v1/inventory/credentials",
            json={"name": "lab", "credential_type": "userpass", "fields": {"username": "u", "password": "hunter2"}},
            headers=plain,
        )
        assert created.status_code in (200, 201), created.text
        url = f"/api/v1/inventory/credentials/{created.json()['id']}/secret"

        refused = client.get(url, headers=plain)
        assert refused.status_code == 403
        assert "hunter2" not in refused.text

        admin = client.get(url, headers={"Authorization": f"Bearer {token(realm_access={'roles': ['acex-admin']})}"})
        assert admin.status_code == 200 and admin.json()["fields"]["password"] == "hunter2"

        service = client.get(
            url, headers={"Authorization": f"Bearer {token(resource_access={'acex': {'roles': ['acex-service']}})}"}
        )
        assert service.status_code == 200

        assert client.get(url).status_code == 401
