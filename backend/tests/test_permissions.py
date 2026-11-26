"""The permissions the framework names, and the roles that hold them.

The framework says what can be allowed; whoever runs an installation makes the roles. A role in a token is a bundle of
the settings (or one of the two that come with the framework), a permission, or a pattern of permissions.
"""

import json
from pathlib import Path

import pytest
from acex import permissions
from acex.api import auth
from acex.permissions import PERMISSIONS, expand, keycloak_roles, matches, resolve_bundles
from acex.settings import AuthorizationSettings, Settings

ISSUER = "https://keycloak.example/realms/acex"
ROLE_NAMES = {"admin": "acex-admin", "service": "acex-service"}
KEYCLOAK_CLAIMS = ("realm_access.roles", "resource_access.{audience}.roles")
DOCS = Path(__file__).resolve().parents[2] / "docs" / "guides" / "api-faq.md"


@pytest.fixture(autouse=True)
def _reset_auth():
    yield
    auth.configure(None)
    auth.configure_authorization("off", KEYCLOAK_CLAIMS, ROLE_NAMES)


class TestTheVocabulary:
    def should_name_each_permission_by_an_area_and_what_it_allows(self):
        for name in PERMISSIONS:
            area, _, rest = name.partition(".")
            assert area and rest and name == name.lower() and " " not in name, name

    def should_give_each_permission_to_a_group_with_a_mode_of_its_own(self):
        for permission in PERMISSIONS.values():
            assert permission.group in permissions.MODE_SETTINGS, permission.name

    def should_say_in_a_sentence_what_each_allows(self):
        for permission in PERMISSIONS.values():
            assert len(permission.summary) > 20 and not permission.summary.endswith("."), permission.name

    def should_hold_the_login_of_a_worker_only_by_the_service_role(self):
        # A person does not need the broker's login, and a worker does not order commands.
        assert not PERMISSIONS["workers.connect"].admin and PERMISSIONS["workers.connect"].service
        assert not PERMISSIONS["workers.report"].admin and PERMISSIONS["workers.report"].service
        assert not PERMISSIONS["operations.execute"].service
        assert not PERMISSIONS["operations.apply"].service


class TestMatches:
    @pytest.mark.parametrize(
        ("role", "permission", "expected"),
        [
            ("operations.execute", "operations.execute", True),
            ("operations.execute", "operations.apply", False),
            ("operations.*", "operations.execute", True),
            ("operations.*", "operations.runs.read", True),
            ("operations.*", "workflows.run", False),
            ("operations.*", "operations", False),
            ("*", "workers.connect", True),
            ("acex-admin", "operations.execute", False),
            ("operations", "operations.execute", False),
            ("operations.exec*", "operations.execute", False),
        ],
    )
    def should_cover_a_name_a_prefix_or_everything(self, role, permission, expected):
        assert matches(role, permission) is expected


class TestExpand:
    def should_give_the_permissions_a_list_stands_for(self):
        assert expand(["operations.inspect", "workflows.*"]) == {
            "operations.inspect",
            "workflows.edit",
            "workflows.run",
            "workflows.runs.read",
            "workflows.runs.browse",
        }

    def should_read_one_string_of_names(self):
        assert expand("operations.inspect, operations.runs.read") == {"operations.inspect", "operations.runs.read"}

    def should_refuse_a_name_that_is_no_permission(self):
        with pytest.raises(ValueError, match="'operations.exectue' is not a permission"):
            expand(["operations.exectue"])

    def should_refuse_a_pattern_that_covers_nothing(self):
        with pytest.raises(ValueError, match="'nothing.*' is not a permission"):
            expand(["nothing.*"])

    def should_say_where_the_mistake_is_and_which_names_there_are(self):
        with pytest.raises(ValueError, match=r"ACEX_AUTHZ_BUNDLES, role 'op'.*operations\.execute"):
            expand(["x"], where="ACEX_AUTHZ_BUNDLES, role 'op'")


class TestBundles:
    def should_come_with_the_two_default_roles(self):
        bundles = resolve_bundles(ROLE_NAMES)
        assert set(bundles) == {"acex-admin", "acex-service"}
        assert bundles["acex-admin"] == {name for name, p in PERMISSIONS.items() if p.admin}
        assert bundles["acex-service"] == {name for name, p in PERMISSIONS.items() if p.service}

    def should_use_the_names_the_settings_give_the_default_roles(self):
        assert set(resolve_bundles({"admin": "netops", "service": "robots"})) == {"netops", "robots"}

    def should_add_the_roles_of_the_settings(self):
        bundles = resolve_bundles(ROLE_NAMES, {"inspector": ["operations.inspect", "operations.runs.read"]})
        assert bundles["inspector"] == {"operations.inspect", "operations.runs.read"}
        assert "acex-admin" in bundles

    def should_expand_a_pattern_in_a_role_of_the_settings(self):
        bundles = resolve_bundles(ROLE_NAMES, {"operations": ["operations.*"], "everything": ["*"]})
        assert bundles["operations"] == {name for name in PERMISSIONS if name.startswith("operations.")}
        assert bundles["everything"] == set(PERMISSIONS)

    def should_let_a_role_of_the_settings_replace_a_default_role(self):
        assert resolve_bundles(ROLE_NAMES, {"acex-admin": ["operations.inspect"]})["acex-admin"] == {
            "operations.inspect"
        }

    @pytest.mark.parametrize("name", ["operations.execute", "operations.*", "*"])
    def should_refuse_a_role_named_as_a_permission_or_a_pattern(self, name):
        with pytest.raises(ValueError, match="needs a name of its own"):
            resolve_bundles(ROLE_NAMES, {name: ["operations.inspect"]})

    def should_refuse_a_permission_that_does_not_exist(self):
        with pytest.raises(ValueError, match="role 'inspector'.*'operations.inspekt'"):
            resolve_bundles(ROLE_NAMES, {"inspector": ["operations.inspekt"]})


def _claims(*roles, path=("realm_access", "roles")):
    body: dict = {"sub": "someone"}
    cursor = body
    for key in path[:-1]:
        cursor = cursor.setdefault(key, {})
    cursor[path[-1]] = list(roles)
    return body


class TestPermissionsOfAToken:
    @pytest.fixture(autouse=True)
    def _configured(self):
        auth.configure(ISSUER, "acex")
        auth.configure_authorization(
            "enforce",
            KEYCLOAK_CLAIMS,
            ROLE_NAMES,
            "enforce",
            {"inspector": ["operations.inspect", "operations.runs.read"], "ops": ["operations.*"]},
        )

    def should_give_what_a_default_role_holds(self):
        assert auth.permissions_of(_claims("acex-service")) == {
            "credentials.reveal",
            "workflows.runs.read",
            "workers.connect",
            "workers.report",
        }

    def should_give_what_a_role_of_the_settings_holds(self):
        assert auth.permissions_of(_claims("inspector")) == {"operations.inspect", "operations.runs.read"}

    def should_count_a_role_that_is_a_permission(self):
        assert auth.permissions_of(_claims("workflows.run")) == {"workflows.run"}

    def should_count_a_role_that_is_a_pattern(self):
        assert auth.permissions_of(_claims("workflows.*")) == {
            "workflows.edit",
            "workflows.run",
            "workflows.runs.read",
            "workflows.runs.browse",
        }

    def should_add_the_permissions_of_every_role(self):
        assert auth.permissions_of(_claims("inspector", "workflows.run")) == {
            "operations.inspect",
            "operations.runs.read",
            "workflows.run",
        }

    def should_give_nothing_for_a_role_that_is_none_of_them(self):
        assert auth.permissions_of(_claims("offline_access", "uma_authorization", "acex-viewer")) == set()
        assert auth.permissions_of({}) == set()

    def should_read_a_client_role_of_the_audience_as_well(self):
        # A client role of `acex` named as a permission is how a composite role in Keycloak shows up in a token.
        claims = _claims("operations.inspect", path=("resource_access", "acex", "roles"))
        assert auth.permissions_of(claims) == {"operations.inspect"}

    def should_not_read_a_client_role_of_another_client(self):
        claims = _claims("operations.inspect", path=("resource_access", "other", "roles"))
        assert auth.permissions_of(claims) == set()

    def should_know_the_roles_of_an_installation_after_it_is_configured_again(self):
        auth.configure_authorization("enforce", KEYCLOAK_CLAIMS, ROLE_NAMES)
        assert auth.permissions_of(_claims("inspector")) == set()


class TestSettings:
    def should_have_no_roles_of_its_own_unless_asked(self):
        assert AuthorizationSettings().bundles == {}

    def should_read_one_variable_for_each_role(self, monkeypatch):
        monkeypatch.setenv("ACEX_AUTHZ_BUNDLES__INSPECTOR", "operations.inspect, operations.runs.read")
        monkeypatch.setenv("ACEX_AUTHZ_BUNDLES__OPS", '["operations.*"]')
        assert Settings().authz.bundles == {
            "inspector": ["operations.inspect", "operations.runs.read"],
            "ops": ["operations.*"],
        }

    def should_read_the_roles_as_json(self, monkeypatch):
        monkeypatch.setenv(
            "ACEX_AUTHZ_BUNDLES",
            '{"inspector": ["operations.inspect"], "network-operator": "workflows.run,workflows.edit"}',
        )
        assert Settings().authz.bundles == {
            "inspector": ["operations.inspect"],
            "network-operator": ["workflows.run", "workflows.edit"],
        }

    def should_stop_the_api_from_starting_on_a_permission_that_does_not_exist(self):
        with pytest.raises(ValueError, match="operations.exectue"):
            auth.configure_authorization("off", KEYCLOAK_CLAIMS, ROLE_NAMES, "off", {"ops": ["operations.exectue"]})

    def should_keep_the_old_roles_when_a_new_configuration_is_refused(self):
        auth.configure_authorization("off", KEYCLOAK_CLAIMS, ROLE_NAMES, "off", {"ops": ["operations.inspect"]})
        with pytest.raises(ValueError):
            auth.configure_authorization("enforce", KEYCLOAK_CLAIMS, ROLE_NAMES, "enforce", {"x": ["nothing"]})
        assert auth.AUTHZ_MODE == "off"
        assert "ops" in auth.authorization_overview()["roles"]


class TestOverview:
    def should_list_every_permission_with_the_roles_that_hold_it(self):
        auth.configure_authorization(
            "log", KEYCLOAK_CLAIMS, ROLE_NAMES, "enforce", {"inspector": ["operations.inspect"]}
        )
        overview = auth.authorization_overview()

        assert [p["name"] for p in overview["permissions"]] == list(PERMISSIONS)
        by_name = {p["name"]: p for p in overview["permissions"]}
        assert by_name["operations.inspect"]["roles"] == ["acex-admin", "inspector"]
        assert by_name["workers.connect"]["roles"] == ["acex-service"]
        assert by_name["operations.execute"]["sensitive"] is True
        assert overview["roles"]["inspector"] == ["operations.inspect"]
        assert overview["modes"] == {
            "credentials": {"setting": "ACEX_AUTHZ_MODE", "mode": "log"},
            "operations": {"setting": "ACEX_AUTHZ_OPERATIONS_MODE", "mode": "enforce"},
        }
        assert overview["roles_claims"] == list(KEYCLOAK_CLAIMS)


class TestForTheIdentityProvider:
    def should_give_the_permissions_as_client_roles_to_import_into_a_realm(self):
        roles = keycloak_roles("acex")
        assert roles["ifResourceExists"] == "SKIP"
        listed = roles["roles"]["client"]["acex"]
        assert [role["name"] for role in listed] == list(PERMISSIONS)
        assert all(role["description"].startswith("Allows to ") for role in listed)

    def should_ship_the_same_client_roles_in_the_realm_of_the_docker_compose_setup(self):
        realm = json.loads((DOCS.parents[2] / "keycloak" / "realm-export.json").read_text())
        shipped = realm["roles"]["client"]["acex"]
        assert shipped == keycloak_roles("acex")["roles"]["client"]["acex"], "run: python -m acex.permissions keycloak"

    def should_name_the_client_asked_for(self):
        assert list(keycloak_roles("other")["roles"]["client"]) == ["other"]

    def should_print_it_from_the_command_line(self, capsys):
        assert permissions.main(["keycloak"]) == 0
        assert json.loads(capsys.readouterr().out) == keycloak_roles("acex")
        assert permissions.main(["keycloak", "mine"]) == 0
        assert list(json.loads(capsys.readouterr().out)["roles"]["client"]) == ["mine"]

    def should_print_the_table_from_the_command_line(self, capsys):
        assert permissions.main(["table"]) == 0
        assert capsys.readouterr().out.strip() == permissions.table()

    def should_say_how_to_use_it_when_asked_for_nothing_it_knows(self, capsys):
        assert permissions.main([]) == 2
        assert permissions.main(["nonsense"]) == 2
        assert "python -m acex.permissions table" in capsys.readouterr().err


class TestDocumentation:
    def should_have_the_table_of_the_code_in_the_api_faq(self):
        text = DOCS.read_text()
        start, end = "<!-- permissions:start -->", "<!-- permissions:end -->"
        assert start in text and end in text, "the table of permissions goes between the two markers"
        written = text.split(start)[1].split(end)[0].strip()
        assert written == permissions.table(), "run: python -m acex.permissions table"

    def should_have_a_table_that_names_the_default_roles_as_the_settings_do(self):
        table = permissions.table({"admin": "netops", "service": "robots"})
        assert "`netops`" in table and "`robots`" in table and "acex-admin" not in table
