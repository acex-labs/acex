"""The permissions the framework names, and how a token comes to hold them.

The framework says what can be allowed and which route needs what. It names no roles: a token holds a permission when
one of its roles is the permission, or a pattern that covers it, which is how a role made of permissions in the identity
provider reaches a token. Where the identity provider cannot make such a role, the settings can name roles and what
each holds.
"""

import json
import re
from pathlib import Path

import pytest
from acex import permissions
from acex.api import auth
from acex.permissions import PERMISSIONS, expand, keycloak_roles, matches, resolve_bundles
from acex.settings import AuthorizationSettings, Settings

ISSUER = "https://keycloak.example/realms/acex"
KEYCLOAK_CLAIMS = ("realm_access.roles", "resource_access.{audience}.roles")
REPOSITORY = Path(__file__).resolve().parents[2]
DOCS = REPOSITORY / "docs" / "guides" / "api-faq.md"
DEV_REALM = REPOSITORY / "keycloak" / "realm-export.json"


@pytest.fixture(autouse=True)
def _reset_auth():
    yield
    auth.configure(None)
    auth.configure_authorization("off", KEYCLOAK_CLAIMS)


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


class TestRolesOfTheSettings:
    def should_be_none_unless_the_settings_name_some(self):
        assert resolve_bundles() == {}
        assert resolve_bundles({}) == {}

    def should_hold_what_the_settings_list_for_each(self):
        assert resolve_bundles({"inspector": ["operations.inspect", "operations.runs.read"]}) == {
            "inspector": {"operations.inspect", "operations.runs.read"}
        }

    def should_expand_a_pattern(self):
        bundles = resolve_bundles({"operations": ["operations.*"], "everything": ["*"]})
        assert bundles["operations"] == {name for name in PERMISSIONS if name.startswith("operations.")}
        assert bundles["everything"] == set(PERMISSIONS)

    @pytest.mark.parametrize("name", ["operations.execute", "operations.*", "*"])
    def should_refuse_a_role_named_as_a_permission_or_a_pattern(self, name):
        with pytest.raises(ValueError, match="needs a name of its own"):
            resolve_bundles({name: ["operations.inspect"]})

    def should_refuse_a_permission_that_does_not_exist(self):
        with pytest.raises(ValueError, match="role 'inspector'.*'operations.inspekt'"):
            resolve_bundles({"inspector": ["operations.inspekt"]})


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
            "enforce",
            {"inspector": ["operations.inspect", "operations.runs.read"], "ops": ["operations.*"]},
        )

    def should_count_a_role_that_is_a_permission(self):
        assert auth.permissions_of(_claims("workflows.run")) == {"workflows.run"}

    def should_count_a_role_that_is_a_pattern(self):
        assert auth.permissions_of(_claims("workflows.*")) == {
            "workflows.edit",
            "workflows.run",
            "workflows.runs.read",
            "workflows.runs.browse",
        }

    def should_read_a_client_role_of_the_audience_as_well(self):
        claims = _claims("operations.inspect", path=("resource_access", "acex", "roles"))
        assert auth.permissions_of(claims) == {"operations.inspect"}

    def should_not_read_a_client_role_of_another_client(self):
        claims = _claims("operations.inspect", path=("resource_access", "other", "roles"))
        assert auth.permissions_of(claims) == set()

    def should_hold_what_keycloak_lists_for_a_role_made_of_permissions(self):
        # Keycloak names such a role among the realm roles and what it is made of among the roles of the client.
        claims = {
            "realm_access": {"roles": ["network-operator", "offline_access"]},
            "resource_access": {"acex": {"roles": ["operations.inspect", "workflows.run"]}},
        }
        assert auth.permissions_of(claims) == {"operations.inspect", "workflows.run"}

    def should_give_what_a_role_of_the_settings_holds(self):
        assert auth.permissions_of(_claims("inspector")) == {"operations.inspect", "operations.runs.read"}

    def should_add_the_permissions_of_every_role(self):
        assert auth.permissions_of(_claims("inspector", "workflows.run")) == {
            "operations.inspect",
            "operations.runs.read",
            "workflows.run",
        }

    def should_give_nothing_for_a_role_that_is_none_of_them(self):
        assert auth.permissions_of(_claims("offline_access", "uma_authorization", "acex-viewer")) == set()
        assert auth.permissions_of({}) == set()

    @pytest.mark.parametrize("path", [("realm_access", "roles"), ("resource_access", "acex", "roles")])
    def should_give_nothing_for_the_names_of_the_roles_the_backend_once_had(self, path):
        assert auth.permissions_of(_claims("acex-admin", "acex-service", "admin", "service", path=path)) == set()

    def should_know_the_roles_of_an_installation_after_it_is_configured_again(self):
        auth.configure_authorization("enforce", KEYCLOAK_CLAIMS)
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
            auth.configure_authorization("off", KEYCLOAK_CLAIMS, "off", {"ops": ["operations.exectue"]})

    def should_keep_the_old_roles_when_a_new_configuration_is_refused(self):
        auth.configure_authorization("off", KEYCLOAK_CLAIMS, "off", {"ops": ["operations.inspect"]})
        with pytest.raises(ValueError):
            auth.configure_authorization("enforce", KEYCLOAK_CLAIMS, "enforce", {"x": ["nothing"]})
        assert auth.AUTHZ_MODE == "off"
        assert "ops" in auth.authorization_overview()["roles"]

    def should_refuse_what_is_not_a_mode(self):
        # The call used to name the two roles in the third place, where the mode of the operations routes is now.
        with pytest.raises(ValueError, match="is not a mode"):
            auth.configure_authorization("off", KEYCLOAK_CLAIMS, {"admin": "acex-admin", "service": "acex-service"})
        with pytest.raises(ValueError, match="'strict' is not a mode"):
            auth.configure_authorization("strict", KEYCLOAK_CLAIMS)
        assert (auth.AUTHZ_MODE, auth.OPERATIONS_AUTHZ_MODE) == ("off", "off")


#: The settings that named the two roles the backend once had of its own.
ADMIN_ROLE, SERVICE_ROLE = "ACEX_AUTHZ_ADMIN_ROLE", "ACEX_AUTHZ_SERVICE_ROLE"


class TestASettingThatNamedARoleOfTheBackend:
    """Nobody is let in under such a name any more. With a check on, starting and refusing every caller that had the
    role would be worse than not starting."""

    @pytest.fixture(autouse=True)
    def _clean(self, monkeypatch):
        for name in (ADMIN_ROLE, SERVICE_ROLE, "ACEX_AUTHZ_MODE", "ACEX_AUTHZ_OPERATIONS_MODE"):
            monkeypatch.delenv(name, raising=False)

    @pytest.mark.parametrize("variable", [ADMIN_ROLE, SERVICE_ROLE])
    @pytest.mark.parametrize(
        ("check", "mode"),
        [
            ("ACEX_AUTHZ_MODE", "log"),
            ("ACEX_AUTHZ_MODE", "enforce"),
            ("ACEX_AUTHZ_OPERATIONS_MODE", "log"),
            ("ACEX_AUTHZ_OPERATIONS_MODE", "enforce"),
        ],
    )
    def should_stop_the_api_from_starting_while_a_check_is_on(self, monkeypatch, variable, check, mode):
        monkeypatch.setenv(variable, "netops")
        monkeypatch.setenv(check, mode)
        with pytest.raises(ValueError, match=f"{variable} is no longer read: the backend names no roles") as refused:
            Settings()
        assert "ACEX_AUTHZ_BUNDLES" in str(refused.value) and "remove the variable" in str(refused.value)

    def should_name_both_when_both_are_left(self, monkeypatch):
        monkeypatch.setenv(ADMIN_ROLE, "acex-admin")
        monkeypatch.setenv(SERVICE_ROLE, "acex-service")
        with pytest.raises(ValueError, match=f"{ADMIN_ROLE} and {SERVICE_ROLE} are no longer read"):
            Settings(authz={"mode": "enforce"})

    def should_stop_for_a_mode_given_in_code_as_well(self, monkeypatch):
        monkeypatch.setenv(SERVICE_ROLE, "robots")
        with pytest.raises(ValueError, match="no longer read"):
            AuthorizationSettings(operations_mode="enforce")

    def should_let_it_be_while_nothing_is_checked(self, monkeypatch):
        # It did nothing before either: a copy of the old .env.example has both.
        monkeypatch.setenv(ADMIN_ROLE, "acex-admin")
        monkeypatch.setenv(SERVICE_ROLE, "acex-service")
        settings = Settings().authz
        assert (settings.mode, settings.operations_mode) == ("off", "off")

    def should_count_an_empty_one_as_not_set(self, monkeypatch):
        monkeypatch.setenv(ADMIN_ROLE, "")
        assert Settings(authz={"mode": "enforce"}).authz.mode == "enforce"

    def should_start_with_a_check_on_when_none_is_left(self):
        assert Settings(authz={"mode": "enforce", "operations_mode": "log"}).authz.operations_mode == "log"

    @pytest.mark.parametrize("field", ["admin_role", "service_role"])
    def should_not_take_the_name_of_a_role_in_code_either(self, field):
        with pytest.raises(ValueError, match=field):
            AuthorizationSettings(**{field: "netops"})


class TestOverview:
    def should_list_every_permission_and_how_the_checks_are_set(self):
        auth.configure_authorization("log", KEYCLOAK_CLAIMS, "enforce")
        overview = auth.authorization_overview()

        assert [p["name"] for p in overview["permissions"]] == list(PERMISSIONS)
        by_name = {p["name"]: p for p in overview["permissions"]}
        assert by_name["operations.execute"]["sensitive"] is True
        assert by_name["operations.inspect"]["sensitive"] is False
        assert by_name["credentials.reveal"]["group"] == "credentials"
        assert overview["modes"] == {
            "credentials": {"setting": "ACEX_AUTHZ_MODE", "mode": "log"},
            "operations": {"setting": "ACEX_AUTHZ_OPERATIONS_MODE", "mode": "enforce"},
        }
        assert overview["roles_claims"] == list(KEYCLOAK_CLAIMS)

    def should_name_no_roles_unless_the_settings_do(self):
        auth.configure_authorization("enforce", KEYCLOAK_CLAIMS, "enforce")
        overview = auth.authorization_overview()

        assert overview["roles"] == {}
        assert all(p["roles"] == [] for p in overview["permissions"])

    def should_list_the_roles_of_the_settings_with_what_they_hold(self):
        auth.configure_authorization(
            "off", KEYCLOAK_CLAIMS, "off", {"inspector": ["operations.inspect"], "ops": ["operations.*"]}
        )
        overview = auth.authorization_overview()

        by_name = {p["name"]: p for p in overview["permissions"]}
        assert by_name["operations.inspect"]["roles"] == ["inspector", "ops"]
        assert by_name["operations.execute"]["roles"] == ["ops"]
        assert by_name["workers.connect"]["roles"] == []
        assert overview["roles"]["inspector"] == ["operations.inspect"]
        assert set(overview["roles"]) == {"inspector", "ops"}


class TestForTheIdentityProvider:
    def should_give_the_permissions_as_client_roles_to_import_into_a_realm(self):
        roles = keycloak_roles("acex")
        assert roles["ifResourceExists"] == "SKIP"
        listed = roles["roles"]["client"]["acex"]
        assert [role["name"] for role in listed] == list(PERMISSIONS)
        assert all(role["description"].startswith("Allows to ") for role in listed)

    def should_make_no_roles_of_them(self):
        # Which permissions go together in a role is for whoever runs the installation to say.
        assert set(keycloak_roles("acex")["roles"]) == {"client"}

    def should_ship_the_same_client_roles_in_the_realm_of_the_docker_compose_setup(self):
        realm = json.loads(DEV_REALM.read_text())
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


#: A permission, or a pattern of them, as the documentation writes one: in backticks or, in an example of a setting, in
#: quotes or after an equals sign or a comma.
_WRITTEN = re.compile(r"(?<=[`\"=,])(?:credentials|operations|workflows|workers)\.[a-z.*]+(?=[`\",\n])")
_BUNDLES_AS_JSON = re.compile(r"ACEX_AUTHZ_BUNDLES='(\{.*?\})'")


class TestDocumentation:
    def should_have_the_table_of_the_code_in_the_api_faq(self):
        text = DOCS.read_text()
        start, end = "<!-- permissions:start -->", "<!-- permissions:end -->"
        assert start in text and end in text, "the table of permissions goes between the two markers"
        written = text.split(start)[1].split(end)[0].strip()
        assert written == permissions.table(), "run: python -m acex.permissions table"

    def should_have_a_line_in_the_table_for_each_permission_and_no_column_of_roles(self):
        header, _, *rows = permissions.table().splitlines()
        assert header == "| Permission | Allows to |"
        assert [row.split("|")[1].strip() for row in rows] == [f"`{name}`" for name in PERMISSIONS]

    def should_write_only_permissions_that_exist_in_the_api_faq(self):
        written = set(_WRITTEN.findall(DOCS.read_text()))
        assert len(written) >= len(PERMISSIONS), "the pattern no longer finds what the guide writes"
        for name in written:
            assert expand([name]), name

    def should_give_examples_of_the_setting_in_the_api_faq_that_the_api_starts_with(self):
        examples = _BUNDLES_AS_JSON.findall(DOCS.read_text())
        assert len(examples) >= 2, "the guide shows a role of one's own, and the two old roles for an upgrade"
        for example in examples:
            assert resolve_bundles(AuthorizationSettings(bundles=json.loads(example)).bundles)

    def should_say_in_the_api_faq_how_the_two_old_roles_keep_reading_logins(self):
        # The one check there was let both roles read a device login; the guide's line for an upgrade must do the same.
        bridges = [
            json.loads(example) for example in _BUNDLES_AS_JSON.findall(DOCS.read_text()) if "acex-admin" in example
        ]
        assert len(bridges) == 1
        resolved = resolve_bundles(bridges[0])
        assert set(resolved) == {"acex-admin", "acex-service"}
        assert all("credentials.reveal" in held for held in resolved.values())
