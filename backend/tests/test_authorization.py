"""A device login in the clear is for the agents and workers that need it and for the people who may see it, not for
every valid token: reading one needs the permission `credentials.reveal`.

The check is rolled out in three modes: off (nothing is checked), log (what would be refused is logged) and enforce
(refused with 403). The permissions are read from the roles of the token, in the places the settings name. The backend
knows no role by its name: a role holds the permission because the identity provider made it of permissions, or because
the settings list what it holds.
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
    auth.configure_authorization("off", KEYCLOAK_CLAIMS)


def _client(
    mode: str,
    claims: dict,
    issuer: str | None = ISSUER,
    roles_claims=KEYCLOAK_CLAIMS,
    bundles: dict | None = None,
) -> TestClient:
    auth.configure(issuer, "acex")
    auth.configure_authorization(mode, roles_claims, bundles=bundles)
    app = FastAPI()
    app.include_router(credentials.create_router(FakeEngine()))
    app.dependency_overrides[auth.get_current_user] = lambda: claims
    return TestClient(app)


NO_ROLES = {"sub": "alice", "aud": "acex"}
#: What Keycloak gives someone with a realm role made of permissions: the role by its name among the realm roles, and
#: the permissions it is made of among the roles of the client `acex`.
PERSON = {
    "sub": "alice",
    "realm_access": {"roles": ["acex-admin"]},
    "resource_access": {"acex": {"roles": ["credentials.reveal", "operations.runs.read"]}},
}
AGENT = {
    "sub": "svc",
    "azp": "collection-agent",
    "realm_access": {"roles": ["offline_access", "acex-service"]},
    "resource_access": {"acex": {"roles": ["credentials.reveal"]}},
}
#: The permission given as a role of the realm itself.
REALM_ROLE = {"sub": "carol", "realm_access": {"roles": ["credentials.reveal"]}}
OTHER_PERMISSION = {"sub": "bob", "resource_access": {"acex": {"roles": ["operations.execute"]}}}
OTHER_CLIENTS_ROLE = {"sub": "bob", "resource_access": {"other-client": {"roles": ["credentials.reveal"]}}}
#: The two roles the backend once had, on a token of a realm where they are made of nothing.
NAMES_ONLY = {"sub": "dave", "azp": "collection-agent", "realm_access": {"roles": ["acex-admin", "acex-service"]}}


class TestRolesOfAToken:
    @pytest.fixture(autouse=True)
    def _keycloak(self):
        auth.configure(ISSUER, "acex")
        auth.configure_authorization("enforce", KEYCLOAK_CLAIMS)

    def should_read_the_realm_roles(self):
        assert auth.roles_of(REALM_ROLE) == {"credentials.reveal"}

    def should_read_the_client_roles_of_the_audience(self):
        assert auth.roles_of(OTHER_PERMISSION) == {"operations.execute"}

    def should_not_read_the_roles_of_another_client(self):
        assert auth.roles_of(OTHER_CLIENTS_ROLE) == set()

    def should_read_both_places_at_once(self):
        assert auth.roles_of(PERSON) == {"acex-admin", "credentials.reveal", "operations.runs.read"}

    def should_read_a_path_of_the_settings(self):
        auth.configure_authorization("enforce", ("roles",))
        assert auth.roles_of({"roles": ["credentials.reveal", "x"]}) == {"credentials.reveal", "x"}

    def should_read_a_claim_of_names_in_one_string(self):
        auth.configure_authorization("enforce", ("scope",))
        assert auth.roles_of({"scope": "openid credentials.reveal"}) == {"openid", "credentials.reveal"}

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
    @pytest.mark.parametrize("claims", [NO_ROLES, PERSON, NAMES_ONLY])
    def should_let_every_token_through_as_before(self, claims):
        assert _client("off", claims).get(SECRET).status_code == 200


class TestEnforce:
    @pytest.mark.parametrize("claims", [PERSON, AGENT, REALM_ROLE])
    def should_give_the_secret_to_a_token_that_holds_the_permission(self, claims):
        response = _client("enforce", claims).get(SECRET)
        assert response.status_code == 200
        assert response.json()["fields"] == {"username": "u", "password": "p"}

    @pytest.mark.parametrize("claims", [NO_ROLES, OTHER_PERMISSION, OTHER_CLIENTS_ROLE, NAMES_ONLY])
    def should_refuse_a_valid_token_without_the_permission(self, claims):
        response = _client("enforce", claims).get(SECRET)
        assert response.status_code == 403
        assert response.json()["detail"] == "Requires the permission credentials.reveal"
        assert "password" not in response.text

    def should_leave_the_other_credential_routes_as_they_are(self):
        assert _client("enforce", NO_ROLES).get("/api/v1/inventory/credentials").status_code == 200

    def should_read_the_permission_from_the_scope_of_a_token_when_the_settings_say_so(self):
        scoped, other = {"sub": "x", "scope": "openid credentials.reveal"}, {"sub": "x", "scope": "openid profile"}
        assert _client("enforce", scoped, roles_claims=("scope",)).get(SECRET).status_code == 200
        assert _client("enforce", other, roles_claims=("scope",)).get(SECRET).status_code == 403
        # Not read unless asked for: the default places are the roles.
        assert _client("enforce", scoped).get(SECRET).status_code == 403

    def should_give_it_to_a_role_the_settings_say_holds_it(self):
        bundles = {"robots": ["credentials.reveal"], "planner": ["operations.inspect"]}
        for role, expected in (("robots", 200), ("planner", 403), ("netops", 403)):
            claims = {"sub": "x", "realm_access": {"roles": [role]}}
            assert _client("enforce", claims, bundles=bundles).get(SECRET).status_code == expected, role
        refused = _client("enforce", NO_ROLES, bundles=bundles).get(SECRET)
        assert refused.json()["detail"] == "Requires the permission credentials.reveal (held by the roles robots)"

    def should_keep_the_two_old_roles_reading_logins_when_the_settings_list_what_they_hold(self):
        # What an installation that had the check on sets before it upgrades, unless it makes the roles of permissions
        # in its identity provider.
        bundles = {"acex-admin": ["credentials.reveal"], "acex-service": ["credentials.reveal"]}
        assert _client("enforce", NAMES_ONLY, bundles=bundles).get(SECRET).status_code == 200
        for role in ("acex-admin", "acex-service"):
            claims = {"sub": "x", "resource_access": {"acex": {"roles": [role]}}}
            assert _client("enforce", claims, bundles=bundles).get(SECRET).status_code == 200, role

    def should_not_check_roles_when_there_is_no_issuer(self):
        # Dev mode: nobody has a token, so nobody has roles.
        assert _client("enforce", {}, issuer=None).get(SECRET).status_code == 200

    def should_log_the_refusal(self, caplog):
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            _client("enforce", AGENT | {"resource_access": {}}).get(SECRET)
        assert "denied" in caplog.text and "collection-agent" in caplog.text
        assert "the permission credentials.reveal; its roles are acex-service, offline_access" in caplog.text

    def should_log_that_a_refused_token_lists_no_roles(self, caplog):
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            _client("enforce", NO_ROLES).get(SECRET)
        assert "'alice' does not hold the permission credentials.reveal; it lists no roles" in caplog.text

    def should_clean_and_cut_each_role_it_logs(self, caplog):
        # The names come from the token. A pattern and a group of a directory are written as they are.
        roles = ["operations.*", "/netops/admins", 'bad\nrole "x"', "r" * 200]
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            _client("enforce", {"sub": "x", "realm_access": {"roles": roles}}).get(SECRET)
        [line] = [record.getMessage() for record in caplog.records]
        assert line.endswith("its roles are /netops/admins, bad?role??x?, operations.*, " + "r" * 64)

    def should_log_the_first_roles_of_a_token_that_lists_many(self, caplog):
        roles = [f"group-{n:02}" for n in range(30)]
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            _client("enforce", {"sub": "x", "realm_access": {"roles": roles}}).get(SECRET)
        [line] = [record.getMessage() for record in caplog.records]
        assert line.endswith("its roles are " + ", ".join(roles[:20]) + " and 10 more")
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            _client("enforce", {"sub": "x", "realm_access": {"roles": roles[:20]}}).get(SECRET)
        assert caplog.records[-1].getMessage().endswith("its roles are " + ", ".join(roles[:20]))


class TestLog:
    def should_let_a_token_without_the_permission_through(self):
        assert _client("log", NO_ROLES).get(SECRET).status_code == 200

    def should_say_what_enforce_would_have_refused(self, caplog):
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            _client("log", NO_ROLES).get(SECRET)
        assert "Would be refused" in caplog.text and "alice" in caplog.text
        assert "/credentials/{id}/secret" in caplog.text

    def should_say_which_roles_a_token_that_would_be_refused_has(self, caplog):
        # What whoever upgrades with the check on reads: the role is there, and is made of nothing.
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            assert _client("log", NAMES_ONLY).get(SECRET).status_code == 200
        assert (
            "'collection-agent' does not hold the permission credentials.reveal; its roles are acex-admin, "
            "acex-service. Set ACEX_AUTHZ_MODE=enforce once every caller has a role that holds it."
        ) in caplog.text

    def should_say_it_once_for_a_caller_that_asks_again_and_again(self, caplog):
        client = _client("log", NO_ROLES)
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            for _ in range(5):
                client.get(SECRET)
        assert caplog.text.count("Would be refused") == 1

    def should_say_nothing_about_a_token_that_holds_the_permission(self, caplog):
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            _client("log", PERSON).get(SECRET)
        assert caplog.text == ""


class TestSettings:
    def should_be_off_unless_asked(self):
        assert AuthorizationSettings().mode == "off"

    def should_read_the_environment(self, monkeypatch):
        monkeypatch.setenv("ACEX_AUTHZ_MODE", "enforce")
        monkeypatch.setenv("ACEX_AUTHZ_ROLES_CLAIMS", "groups, realm_access.roles")
        settings = Settings().authz
        assert (settings.mode, settings.roles_claims) == ("enforce", ["groups", "realm_access.roles"])

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

    def should_give_the_secret_only_to_a_token_that_holds_the_permission(self, tokens):
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

        # A role by its name alone, as a realm that has not made it of permissions gives it.
        named = client.get(url, headers={"Authorization": f"Bearer {token(realm_access={'roles': ['acex-admin']})}"})
        assert named.status_code == 403
        assert "hunter2" not in named.text

        person = client.get(url, headers={"Authorization": f"Bearer {token(**PERSON)}"})
        assert person.status_code == 200 and person.json()["fields"]["password"] == "hunter2"

        agent = client.get(url, headers={"Authorization": f"Bearer {token(**AGENT)}"})
        assert agent.status_code == 200

        assert client.get(url).status_code == 401
