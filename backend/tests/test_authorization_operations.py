"""Running commands on devices, reading what they answered and getting the broker's login each need a permission, which
a token holds through a role: the two roles that come with the framework, a role of the settings, or a role that is
itself a permission. They are not for every valid token.

The rules have a setting of their own, ACEX_AUTHZ_OPERATIONS_MODE, off by default whatever the mode of reading a device
login is. Like that one it has three modes: off (nothing is checked), log (what would be refused is logged) and enforce
(refused with 403).
"""

import logging
import re
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from acex.api import auth
from acex.api.routers import credentials, operation_runs, workers, workflows
from acex.jobs import JobManager, JobTypeRegistry, registry
from acex.operations import ACTIONS
from acex.permissions import PERMISSIONS
from acex.settings import AuthorizationSettings, RabbitMQSettings, Settings
from acex_devkit.models.job import JobState
from acex_devkit.models.ned import Capabilities
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

ISSUER = "https://keycloak.example/realms/acex"
ROLE_NAMES = {"admin": "acex-admin", "service": "acex-service"}
KEYCLOAK_CLAIMS = ("realm_access.roles", "resource_access.{audience}.roles")
API = "/api/v1"

NO_ROLES = {"sub": "alice", "aud": "acex"}
ADMIN = {"sub": "alice", "realm_access": {"roles": ["acex-admin"]}}
WORKER = {"sub": "svc", "azp": "acex-worker", "realm_access": {"roles": ["offline_access", "acex-service"]}}
BOTH = {"sub": "carol", "realm_access": {"roles": ["acex-admin", "acex-service"]}}
OTHER_ROLE = {"sub": "bob", "realm_access": {"roles": ["acex-viewer"]}}
TOKENS = {"none": NO_ROLES, "other": OTHER_ROLE, "admin": ADMIN, "worker": WORKER, "both": BOTH}

#: What each of the two roles that come with the framework holds, spelled out here and not read from the code.
ADMIN_HOLDS = frozenset(
    {
        "credentials.reveal",
        "operations.execute",
        "operations.apply",
        "operations.inspect",
        "operations.runs.read",
        "operations.jobs",
        "workflows.edit",
        "workflows.run",
        "workflows.runs.read",
    }
)
SERVICE_HOLDS = frozenset({"credentials.reveal", "workflows.runs.read", "workers.connect", "workers.report"})
HOLDS = {
    "admin": ADMIN_HOLDS,
    "worker": SERVICE_HOLDS,
    "both": ADMIN_HOLDS | SERVICE_HOLDS,
    "none": frozenset(),
    "other": frozenset(),
}

#: What each route needs. Spelled out here, apart from the routers, so that changing a rule there fails a test until the
#: decision is made here too. Paths are the routers' own.
POLICY: dict[tuple[str, str], str] = {
    # Ordering a run puts commands or configuration on devices; its report holds what they answered.
    ("POST", f"{API}/operations/execute"): "operations.execute",
    ("POST", f"{API}/operations/patch/render"): "operations.inspect",
    ("POST", f"{API}/operations/patch/apply"): "operations.apply",
    **{("POST", f"{API}/operations/actions/{action.name}"): "operations.inspect" for action in ACTIONS},
    ("GET", f"{API}/operations/runs"): "operations.runs.read",
    ("GET", f"{API}/operations/runs/{{run_id}}"): "operations.runs.read",
    ("GET", f"{API}/operations/runs/{{run_id}}/report"): "operations.runs.read",
    # Workflows are stored commands: changing one changes what the next run sends.
    ("POST", f"{API}/operations/workflows"): "workflows.edit",
    ("PATCH", f"{API}/operations/workflows/{{workflow_id}}"): "workflows.edit",
    ("DELETE", f"{API}/operations/workflows/{{workflow_id}}"): "workflows.edit",
    ("POST", f"{API}/operations/workflows/{{workflow_id}}/runs"): "workflows.run",
    ("POST", f"{API}/operations/workflows/runs/{{run_id}}/continue"): "workflows.run",
    ("POST", f"{API}/operations/workflows/runs/{{run_id}}/stop"): "workflows.run",
    ("DELETE", f"{API}/operations/workflows/runs/{{run_id}}"): "workflows.run",
    # What a run shows: people read it, and the workers read a run and its artifacts to run its later steps.
    ("GET", f"{API}/operations/workflows/runs"): "workflows.runs.read",
    ("GET", f"{API}/operations/workflows/runs/{{run_id}}"): "workflows.runs.read",
    ("GET", f"{API}/operations/workflows/runs/{{run_id}}/steps/{{job_id}}"): "workflows.runs.read",
    ("GET", f"{API}/operations/workflows/runs/{{run_id}}/artifacts"): "workflows.runs.read",
    # What a worker does.
    ("POST", f"{API}/workers/connect"): "workers.connect",
    ("PATCH", f"{API}/workers/jobs/{{job_id}}"): "workers.report",
    # What people do with jobs.
    ("GET", f"{API}/workers/jobs"): "operations.jobs",
    ("GET", f"{API}/workers/jobs/{{job_id}}"): "operations.jobs",
    ("POST", f"{API}/workers/jobs/{{job_id}}/requeue"): "operations.jobs",
    ("POST", f"{API}/workers/jobs/{{job_id}}/cancel"): "operations.jobs",
    ("DELETE", f"{API}/workers/jobs"): "operations.jobs",
    ("DELETE", f"{API}/workers/jobs/{{job_id}}"): "operations.jobs",
}

#: Routes of the same routers that stay open to every valid token: they answer from the code or from saved
#: definitions and reach no device.
OPEN = {
    ("GET", f"{API}/operations/patch/tree"),
    ("GET", f"{API}/workers/job_types"),
    ("POST", f"{API}/operations/workflows/check"),
    ("GET", f"{API}/operations/workflows"),
    ("GET", f"{API}/operations/workflows/{{workflow_id}}"),
}


@pytest.fixture(autouse=True)
def _reset_auth():
    yield
    auth.configure(None)
    auth.configure_authorization("off", KEYCLOAK_CLAIMS, ROLE_NAMES)


def _configure(
    operations_mode: str, mode: str = "off", issuer: str | None = ISSUER, bundles: dict | None = None
) -> None:
    auth.configure(issuer, "acex")
    auth.configure_authorization(mode, KEYCLOAK_CLAIMS, ROLE_NAMES, operations_mode, bundles)


def _app(engine, describe: bool = False) -> FastAPI:
    """The three routers in an app, which keeps them in `app.state.routers` to look at. The application describes the
    rules of each router before it includes it, and `describe` does the same."""
    app = FastAPI()
    app.state.routers = [module.create_router(engine) for module in (operation_runs, workers, workflows)]
    for router in app.state.routers:
        if describe:
            auth.describe_permission_rules(router)
        app.include_router(router)
    return app


@pytest.fixture
def stub_app(monkeypatch) -> FastAPI:
    """The three routers over an engine that answers anything, for what happens before a handler runs."""
    monkeypatch.setattr(operation_runs, "NEDManager", MagicMock)
    return _app(MagicMock())


def _routes(app: FastAPI):
    """The routes of the routers the app includes: an app keeps an included router as it is, not as its routes."""
    return [route for router in app.state.routers for route in router.routes if isinstance(route, APIRoute)]


def _as(app: FastAPI, claims: dict) -> TestClient:
    app.dependency_overrides[auth.get_current_user] = lambda: claims
    return TestClient(app, raise_server_exceptions=False)


def _call(client: TestClient, method: str, template: str):
    return client.request(method, re.sub(r"\{[^}]+\}", "1", template), json={})


ROUTES = sorted(POLICY.items())
IDS = [f"{method} {path.removeprefix(API)}" for (method, path), _ in ROUTES]


class TestWhichRoutes:
    def should_have_a_rule_for_every_route_that_runs_or_reads_a_run(self, stub_app):
        guarded, unguarded = {}, set()
        for route in _routes(stub_app):
            permissions = [d.dependency.permission for d in route.dependencies if hasattr(d.dependency, "permission")]
            for method in route.methods:
                if permissions:
                    guarded[(method, route.path)] = permissions[0]
                else:
                    unguarded.add((method, route.path))

        assert guarded == POLICY
        # A route added later has to be put in one list or the other.
        assert unguarded == OPEN

    def should_belong_to_the_operations_group(self, stub_app):
        for route in _routes(stub_app):
            for dependency in route.dependencies:
                if hasattr(dependency.dependency, "permission"):
                    assert PERMISSIONS[dependency.dependency.permission].group == "operations"

    def should_need_no_permission_that_nobody_holds(self):
        # A permission no default role holds could only be reached through a role of the settings.
        for permission in set(POLICY.values()):
            assert permission in ADMIN_HOLDS | SERVICE_HOLDS, permission


class TestOff:
    @pytest.mark.parametrize("token", TOKENS)
    @pytest.mark.parametrize(("method", "path"), [key for key, _ in ROUTES], ids=IDS)
    def should_let_every_token_through_as_before(self, stub_app, method, path, token):
        _configure("off")
        assert _call(_as(stub_app, TOKENS[token]), method, path).status_code not in (401, 403)

    def should_not_follow_the_mode_of_reading_a_login(self, stub_app):
        # The credentials rule is switched on; this one is not asked for, so nothing changes for it.
        _configure("off", mode="enforce")
        assert _call(_as(stub_app, NO_ROLES), "POST", f"{API}/operations/execute").status_code not in (401, 403)
        assert _call(_as(stub_app, NO_ROLES), "POST", f"{API}/workers/connect").status_code not in (401, 403)

    def should_be_the_default_of_the_setting(self, monkeypatch):
        monkeypatch.delenv("ACEX_AUTHZ_OPERATIONS_MODE", raising=False)
        assert AuthorizationSettings().operations_mode == "off"


class TestEnforce:
    @pytest.mark.parametrize("token", TOKENS)
    @pytest.mark.parametrize(("method", "path"), [key for key, _ in ROUTES], ids=IDS)
    def should_refuse_a_token_without_the_permission_and_only_that(self, stub_app, method, path, token):
        _configure("enforce")
        needed = POLICY[(method, path)]
        response = _call(_as(stub_app, TOKENS[token]), method, path)
        if needed in HOLDS[token]:
            assert response.status_code not in (401, 403)
        else:
            assert response.status_code == 403
            assert needed in response.json()["detail"]

    def should_name_the_permission_a_route_needs_and_the_roles_that_hold_it(self, stub_app):
        _configure("enforce")
        refused = _call(_as(stub_app, NO_ROLES), "POST", f"{API}/operations/execute")
        assert refused.json()["detail"] == "Requires the permission operations.execute (held by the roles acex-admin)"
        refused = _call(_as(stub_app, NO_ROLES), "POST", f"{API}/operations/workflows/runs/1/continue")
        assert refused.json()["detail"] == "Requires the permission workflows.run (held by the roles acex-admin)"
        refused = _call(_as(stub_app, NO_ROLES), "GET", f"{API}/operations/workflows/runs/1/artifacts")
        assert (
            refused.json()["detail"]
            == "Requires the permission workflows.runs.read (held by the roles acex-admin, acex-service)"
        )

    def should_leave_the_open_routes_open(self, stub_app):
        _configure("enforce")
        client = _as(stub_app, NO_ROLES)
        for method, path in OPEN:
            assert _call(client, method, path).status_code not in (401, 403), (method, path)

    def should_not_follow_the_mode_of_reading_a_login(self, stub_app):
        # Reading a login stays off, and so does nothing else: only this group is switched on.
        _configure("enforce", mode="off")
        assert _call(_as(stub_app, NO_ROLES), "POST", f"{API}/operations/execute").status_code == 403

    def should_use_the_role_names_of_the_settings(self, stub_app):
        auth.configure(ISSUER, "acex")
        auth.configure_authorization("off", ("roles",), {"admin": "netops", "service": "robots"}, "enforce")
        client = _as(stub_app, {"sub": "x", "roles": ["netops"]})
        assert _call(client, "POST", f"{API}/operations/execute").status_code not in (401, 403)
        assert _call(client, "POST", f"{API}/workers/connect").status_code == 403
        client = _as(stub_app, {"sub": "x", "roles": ["robots"]})
        assert _call(client, "POST", f"{API}/workers/connect").status_code not in (401, 403)
        assert _call(client, "POST", f"{API}/operations/execute").status_code == 403

    def should_not_check_roles_when_there_is_no_issuer(self, stub_app):
        # Dev mode: nobody has a token, so nobody has roles.
        _configure("enforce", issuer=None)
        assert _call(_as(stub_app, {}), "POST", f"{API}/operations/execute").status_code not in (401, 403)


class TestLog:
    @pytest.mark.parametrize("token", TOKENS)
    @pytest.mark.parametrize(("method", "path"), [key for key, _ in ROUTES], ids=IDS)
    def should_let_every_token_through(self, stub_app, method, path, token):
        _configure("log")
        assert _call(_as(stub_app, TOKENS[token]), method, path).status_code not in (401, 403)

    def should_say_what_enforce_would_have_refused_and_which_setting_turns_it_on(self, stub_app, caplog):
        _configure("log")
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            _call(_as(stub_app, NO_ROLES), "POST", f"{API}/operations/execute")
        assert "Would be refused (POST /api/v1/operations/execute)" in caplog.text
        assert "'alice'" in caplog.text and "the permission operations.execute" in caplog.text
        assert "ACEX_AUTHZ_OPERATIONS_MODE=enforce" in caplog.text

    def should_say_it_once_per_caller_and_route(self, stub_app, caplog):
        _configure("log")
        client = _as(stub_app, NO_ROLES)
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            for _ in range(5):
                _call(client, "POST", f"{API}/operations/execute")
            _call(client, "DELETE", f"{API}/workers/jobs")
        assert caplog.text.count("Would be refused") == 2

    def should_say_nothing_about_a_token_with_the_role(self, stub_app, caplog):
        _configure("log")
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            _call(_as(stub_app, ADMIN), "POST", f"{API}/operations/execute")
            _call(_as(stub_app, WORKER), "POST", f"{API}/workers/connect")
        assert caplog.text == ""

    def should_name_the_setting_of_reading_a_login_for_that_rule(self, caplog):
        class Engine:
            credential_manager = MagicMock()

        _configure("off", mode="log")
        app = FastAPI()
        app.include_router(credentials.create_router(Engine()))
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            _as(app, NO_ROLES).get(f"{API}/inventory/credentials/1/secret")
        assert "ACEX_AUTHZ_MODE=enforce" in caplog.text and "OPERATIONS" not in caplog.text


def _realm_role(*roles: str) -> dict:
    return {"sub": "someone", "realm_access": {"roles": list(roles)}}


def _allowed_routes(app: FastAPI, claims: dict) -> set[str]:
    """The permissions of the routes a token gets past, as the routes answer it."""
    client = _as(app, claims)
    return {
        permission
        for (method, path), permission in POLICY.items()
        if _call(client, method, path).status_code not in (401, 403)
    }


class TestRolesOfTheInstallation:
    """The roles are the installation's to make: the framework only says which permission a route needs."""

    def should_let_a_role_of_the_settings_do_what_it_holds_and_nothing_else(self, stub_app):
        _configure("enforce", bundles={"planner": ["operations.inspect", "workflows.run"]})
        assert _allowed_routes(stub_app, _realm_role("planner")) == {"operations.inspect", "workflows.run"}

    def should_let_a_role_that_is_a_permission_do_what_it_names(self, stub_app):
        _configure("enforce")
        assert _allowed_routes(stub_app, _realm_role("operations.execute")) == {"operations.execute"}

    def should_read_it_from_a_client_role_of_the_audience_as_keycloak_gives_a_composite_role(self, stub_app):
        _configure("enforce")
        claims = {"sub": "x", "resource_access": {"acex": {"roles": ["operations.inspect", "operations.runs.read"]}}}
        assert _allowed_routes(stub_app, claims) == {"operations.inspect", "operations.runs.read"}

    def should_let_a_pattern_cover_a_whole_area_and_not_another(self, stub_app):
        _configure("enforce")
        assert _allowed_routes(stub_app, _realm_role("operations.*")) == {
            p for p in POLICY.values() if p.startswith("operations.")
        }

    def should_let_a_role_that_is_everything_do_everything(self, stub_app):
        _configure("enforce")
        assert _allowed_routes(stub_app, _realm_role("*")) == set(POLICY.values())

    def should_let_a_role_of_the_settings_replace_a_default_role(self, stub_app):
        _configure("enforce", bundles={"acex-admin": ["operations.inspect"]})
        assert _allowed_routes(stub_app, ADMIN) == {"operations.inspect"}

    def should_add_what_two_roles_hold(self, stub_app):
        _configure("enforce", bundles={"planner": ["operations.inspect"], "runner": ["workflows.run"]})
        assert _allowed_routes(stub_app, _realm_role("planner", "runner")) == {"operations.inspect", "workflows.run"}

    def should_give_a_role_of_the_settings_nothing_in_the_other_group_of_routes(self, stub_app):
        # Reading a login in the clear is another permission, in the group of ACEX_AUTHZ_MODE.
        _configure("enforce", bundles={"planner": ["operations.inspect"]})
        assert "credentials.reveal" not in _allowed_routes(stub_app, _realm_role("planner"))

    def should_not_turn_a_role_of_the_settings_into_a_way_around_the_mode(self, stub_app):
        _configure("off", bundles={"planner": ["operations.inspect"]})
        assert _allowed_routes(stub_app, _realm_role("somebody-else")) == set(POLICY.values())


class TestSettings:
    def should_read_the_environment(self, monkeypatch):
        monkeypatch.setenv("ACEX_AUTHZ_OPERATIONS_MODE", "log")
        settings = Settings().authz
        assert (settings.mode, settings.operations_mode) == ("off", "log")

    def should_refuse_a_mode_it_does_not_know(self):
        with pytest.raises(ValueError):
            AuthorizationSettings(operations_mode="strict")


class TestDocumentation:
    @pytest.fixture
    def described(self, monkeypatch):
        monkeypatch.setattr(operation_runs, "NEDManager", MagicMock)
        _configure("off")
        return _app(MagicMock(), describe=True)

    def should_say_in_each_description_which_permission_a_route_needs_and_who_holds_it(self, described):
        schema = described.openapi()["paths"]

        for (method, path), needed in POLICY.items():
            description = schema[path][method.lower()]["description"]
            assert "ACEX_AUTHZ_OPERATIONS_MODE" in description, (method, path)
            assert f"**Permission:** `{needed}`" in description, (method, path)
            for role, holds in (("acex-admin", ADMIN_HOLDS), ("acex-service", SERVICE_HOLDS)):
                assert (f"`{role}`" in description) == (needed in holds), (method, path, role)

    def should_keep_what_a_route_already_said(self, described):
        description = described.openapi()["paths"][f"{API}/operations/execute"]["post"]["description"]
        assert description.startswith("Run raw commands on each node")

    def should_say_nothing_about_an_open_route(self, described):
        for method, path in OPEN:
            assert "**Permission:**" not in described.openapi()["paths"][path][method.lower()].get("description", "")

    def should_use_the_role_names_of_the_settings(self, monkeypatch):
        monkeypatch.setattr(operation_runs, "NEDManager", MagicMock)
        auth.configure_authorization("off", KEYCLOAK_CLAIMS, {"admin": "netops", "service": "robots"})
        description = _app(MagicMock(), describe=True).openapi()["paths"][f"{API}/workers/connect"]["post"][
            "description"
        ]
        assert "`robots`" in description and "`acex-service`" not in description


# The routes with a real database behind them: what a refusal leaves undone, and what a worker can still do.


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


class _Producer:
    configured = True

    def publish(self, job_type: str, job_id: int) -> None:
        pass


class _Nodes:
    async def get(self, id: str):
        return SimpleNamespace(
            id=int(id), asset=SimpleNamespace(ned_id="Full"), logical_node=SimpleNamespace(hostname=f"sw-{id}")
        )


class _Neds:
    def get_driver_instance(self, name: str):
        return SimpleNamespace(capabilities=Capabilities(operations=["execute"], actions=["ping"]))


BROKER = RabbitMQSettings(host="rabbitmq", port=5672, vhost="acex", user="acex", password="s3cr/et")


@pytest.fixture
def stack(monkeypatch):
    """The routers over a real job manager, on a fresh database."""
    job_types = JobTypeRegistry()
    for job_type in registry:
        if job_type.name.startswith("acex.operations."):
            job_types.register(job_type)
    jobs = JobManager(_Db(), _Producer(), job_types)
    monkeypatch.setattr(operation_runs, "NEDManager", _Neds)
    engine = SimpleNamespace(
        jobs=jobs,
        inventory=SimpleNamespace(node_instances=_Nodes()),
        settings=SimpleNamespace(rabbitmq=BROKER),
        workflows=MagicMock(),
        workflow_runs=MagicMock(),
    )
    return SimpleNamespace(jobs=jobs, app=_app(engine))


EXECUTE = {"node_ids": [1, 2], "commands": ["show version"]}


class TestWithRealJobs:
    def should_leave_no_job_behind_when_a_token_without_the_role_orders_a_command(self, stack):
        _configure("enforce")

        refused = _as(stack.app, NO_ROLES).post(f"{API}/operations/execute", json=EXECUTE)

        assert refused.status_code == 403
        assert stack.jobs.list_jobs(limit=10, offset=0).total == 0

    def should_order_a_command_for_the_admin_role(self, stack):
        _configure("enforce")

        ordered = _as(stack.app, ADMIN).post(f"{API}/operations/execute", json=EXECUTE)

        assert ordered.status_code == 202
        assert ordered.json()["created_by"] == "alice"
        assert stack.jobs.list_jobs(limit=10, offset=0).total == 1

    def should_not_let_the_worker_order_a_command_with_its_own_token(self, stack):
        _configure("enforce")
        assert _as(stack.app, WORKER).post(f"{API}/operations/execute", json=EXECUTE).status_code == 403

    def should_hand_the_broker_login_to_the_worker_only(self, stack):
        _configure("enforce")
        body = {"job_types": ["acex.operations.execute"]}

        refused = _as(stack.app, ADMIN).post(f"{API}/workers/connect", json=body)
        assert refused.status_code == 403
        assert "s3cr/et" not in refused.text
        assert _as(stack.app, NO_ROLES).post(f"{API}/workers/connect", json=body).status_code == 403

        connected = _as(stack.app, WORKER).post(f"{API}/workers/connect", json=body)
        assert connected.status_code == 200
        assert connected.json()["broker"]["password"] == "s3cr/et"

    def should_let_the_worker_claim_and_report_a_job_and_nobody_else(self, stack):
        _configure("enforce")
        ordered = _as(stack.app, ADMIN).post(f"{API}/operations/execute", json={**EXECUTE, "node_ids": [1]}).json()
        [job] = stack.jobs.children(ordered["id"])
        url = f"{API}/workers/jobs/{job.id}"

        for caller in (ADMIN, NO_ROLES):
            assert _as(stack.app, caller).patch(url, json={"state": "running"}).status_code == 403
        assert stack.jobs.get(job.id).state == JobState.queued

        claimed = _as(stack.app, WORKER).patch(url, json={"state": "running"})
        assert claimed.status_code == 200
        assert claimed.json()["data"]["commands"] == ["show version"]
        done = _as(stack.app, WORKER).patch(url, json={"state": "succeeded", "result": {"responses": []}})
        assert done.status_code in (200, 422)

    def should_keep_jobs_from_a_token_that_cannot_purge_them(self, stack):
        _configure("enforce")
        _as(stack.app, ADMIN).post(f"{API}/operations/execute", json=EXECUTE)

        assert _as(stack.app, WORKER).delete(f"{API}/workers/jobs").status_code == 403
        assert _as(stack.app, NO_ROLES).delete(f"{API}/workers/jobs/1").status_code == 403
        assert stack.jobs.list_jobs(limit=10, offset=0).total == 1

        # The run's batch and its two jobs.
        assert _as(stack.app, ADMIN).delete(f"{API}/workers/jobs").json() == {"deleted": 3}

    def should_keep_the_output_of_a_run_from_a_token_without_the_role(self, stack):
        _configure("enforce")
        run = _as(stack.app, ADMIN).post(f"{API}/operations/execute", json=EXECUTE).json()

        for url in (f"{API}/operations/runs", f"{API}/operations/runs/{run['id']}", f"{API}/workers/jobs"):
            assert _as(stack.app, NO_ROLES).get(url).status_code == 403, url
            assert _as(stack.app, ADMIN).get(url).status_code == 200, url
        csv = _as(stack.app, NO_ROLES).get(f"{API}/operations/runs/{run['id']}/report")
        assert csv.status_code == 403

    def should_log_and_go_on_in_log_mode(self, stack, caplog):
        _configure("log")
        with caplog.at_level(logging.WARNING, logger="acex.auth"):
            ordered = _as(stack.app, NO_ROLES).post(f"{API}/operations/execute", json=EXECUTE)
        assert ordered.status_code == 202
        assert "Would be refused" in caplog.text


class TestThroughTheApp:
    """The whole chain: settings, a signed token, the roles in it, and the application that puts the routes together."""

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
            return {"Authorization": "Bearer " + jwt.encode(body, pem, algorithm="RS256", headers={"kid": "test"})}

        def build(operations_mode: str, bundles: dict | None = None):
            settings = Settings(
                oidc={"issuer_url": ISSUER},
                authz={"mode": "off", "operations_mode": operations_mode, "bundles": bundles or {}},
            )
            engine = AutomationEngine(db_connection=Connection(), settings=settings)
            app = engine.create_app()
            return app, TestClient(app, raise_server_exceptions=False)

        yield build, token
        auth.set_dev_mode(False)

    def should_refuse_a_signed_token_without_the_role_on_every_route_that_runs_a_command(self, tokens):
        build, token = tokens
        _, client = build("enforce")
        plain = token()

        for method, path in (
            ("POST", "/operations/execute"),
            ("POST", "/operations/actions/ping"),
            ("POST", "/operations/patch/apply"),
            ("POST", "/operations/workflows/1/runs"),
            ("POST", "/workers/connect"),
            ("DELETE", "/workers/jobs"),
            ("GET", "/operations/runs/1"),
        ):
            assert client.request(method, API + path, json={}, headers=plain).status_code == 403, (method, path)
        assert client.request("POST", API + "/operations/execute", json={}).status_code == 401

    def should_let_the_roles_through_to_the_handler(self, tokens):
        build, token = tokens
        _, client = build("enforce")
        admin = token(realm_access={"roles": ["acex-admin"]})
        service = token(resource_access={"acex": {"roles": ["acex-service"]}})

        # Past the role check each answers for itself: no broker is configured, and there is no such node.
        assert client.post(API + "/operations/execute", json=EXECUTE, headers=admin).status_code in (404, 503)
        assert (
            client.post(
                API + "/workers/connect", json={"job_types": ["acex.operations.execute"]}, headers=service
            ).status_code
            == 503
        )
        assert (
            client.post(
                API + "/workers/connect", json={"job_types": ["acex.operations.execute"]}, headers=admin
            ).status_code
            == 403
        )

    def should_check_nothing_while_the_setting_is_off(self, tokens):
        build, token = tokens
        _, client = build("off")
        assert (
            client.post(
                API + "/workers/connect", json={"job_types": ["acex.operations.execute"]}, headers=token()
            ).status_code
            == 503
        )

    def should_give_a_signed_token_the_permissions_of_the_roles_of_the_settings(self, tokens):
        build, token = tokens
        _, client = build("enforce", {"planner": ["operations.inspect"]})
        planner = token(realm_access={"roles": ["planner"]})

        # Past the check each answers for itself: there is no such node, and no broker.
        assert client.post(API + "/operations/patch/render", json={}, headers=planner).status_code not in (401, 403)
        assert client.post(API + "/operations/execute", json=EXECUTE, headers=planner).status_code == 403
        composite = token(resource_access={"acex": {"roles": ["operations.execute"]}})
        assert client.post(API + "/operations/execute", json=EXECUTE, headers=composite).status_code in (404, 503)
        assert client.post(API + "/operations/patch/apply", json={}, headers=composite).status_code == 403

    def should_list_the_permissions_and_the_roles_for_any_valid_token(self, tokens):
        build, token = tokens
        _, client = build("log", {"planner": ["operations.inspect"]})

        assert client.get(API + "/auth/permissions").status_code == 401
        listed = client.get(API + "/auth/permissions", headers=token())
        assert listed.status_code == 200
        body = listed.json()
        assert {p["name"] for p in body["permissions"]} == set(PERMISSIONS)
        assert body["roles"]["planner"] == ["operations.inspect"]
        assert body["modes"]["operations"] == {"setting": "ACEX_AUTHZ_OPERATIONS_MODE", "mode": "log"}

    def should_refuse_to_start_on_a_role_of_the_settings_with_a_permission_that_does_not_exist(self, tokens):
        build, _ = tokens
        with pytest.raises(ValueError, match="operations.exectue"):
            build("enforce", {"planner": ["operations.exectue"]})

    def should_describe_the_rules_in_the_applications_documentation(self, tokens, monkeypatch):
        build, _ = tokens
        monkeypatch.setattr(auth, "_get_discovery", lambda: None)
        app, _ = build("off")
        paths = app.openapi()["paths"]
        assert "ACEX_AUTHZ_OPERATIONS_MODE" in paths[f"{API}/operations/execute"]["post"]["description"]
        assert "ACEX_AUTHZ_MODE" in paths[f"{API}/inventory/credentials/{{id}}/secret"]["get"]["description"]
