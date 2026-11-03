"""Runs of operations on nodes: ordered only for nodes whose driver can run them, read back as a report
of each node's response sorted by hostname, and downloadable."""

from types import SimpleNamespace

import pytest
from acex.api import auth
from acex.api.routers import operation_runs
from acex.jobs import JobManager, JobTypeRegistry, registry
from acex_devkit.models.job import JobState, JobUpdate
from acex_devkit.models.ned import Capabilities
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

OPS = "/api/v1/operations"


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


class _Producer:
    def __init__(self, configured: bool = True):
        self.configured = configured

    def publish(self, job_type: str, job_id: int) -> None:
        pass


class _Nodes:
    """Node 1 sw-b and node 2 sw-a run a driver with execute, ping and config read and write; node 3 one that
    only reads config."""

    NODES = {1: ("sw-b", "Full"), 2: ("sw-a", "Full"), 3: ("old", "Bare")}

    async def get(self, id: str):
        if int(id) not in self.NODES:
            raise HTTPException(status_code=404, detail=f"Node instance {id} not found")
        hostname, ned = self.NODES[int(id)]
        return SimpleNamespace(
            id=int(id), asset=SimpleNamespace(ned_id=ned), logical_node=SimpleNamespace(hostname=hostname)
        )


class _Neds:
    CAPABILITIES = {
        "Full": Capabilities(operations=["apply", "execute", "get_config"], actions=["ping"]),
        "Bare": Capabilities(operations=["get_config"]),
    }

    def get_driver_instance(self, name: str):
        return SimpleNamespace(capabilities=self.CAPABILITIES[name])


class _Api:
    def __init__(self, monkeypatch, configured: bool = True):
        job_types = JobTypeRegistry()
        for job_type in registry:
            if job_type.name.startswith("acex.operations."):
                job_types.register(job_type)
        self.jobs = JobManager(_Db(), _Producer(configured), job_types)
        monkeypatch.setattr(operation_runs, "NEDManager", _Neds)
        engine = SimpleNamespace(jobs=self.jobs, inventory=SimpleNamespace(node_instances=_Nodes()))
        app = FastAPI()
        app.include_router(operation_runs.create_router(engine))
        app.dependency_overrides[auth.get_current_user] = lambda: {"sub": "alice"}
        self.client = TestClient(app)

    def finish(self, run_id: int, results: dict[int, dict | str]) -> None:
        """Report each node's job: a dict succeeds with it as result, a string fails with it as error."""
        for job in self.jobs.children(run_id):
            self.jobs.update(job.id, JobUpdate(state=JobState.running), worker="w")
            outcome = results[job.subject_id]
            report = (
                JobUpdate(state=JobState.succeeded, result=outcome)
                if isinstance(outcome, dict)
                else JobUpdate(state=JobState.failed, error=outcome)
            )
            self.jobs.update(job.id, report, worker="w")


@pytest.fixture
def api(monkeypatch) -> _Api:
    return _Api(monkeypatch)


PING = {"node_ids": [1, 2], "params": {"target": "10.0.0.1", "count": 5, "vrf": "MGMT", "size": 1500}}


def test_execute_orders_a_run(api):
    response = api.client.post(f"{OPS}/execute", json={"node_ids": [1, 2, 1], "commands": [" show version "]})

    assert response.status_code == 202
    run = response.json()
    assert (run["type"], run["jobs"]["queued"], run["created_by"]) == ("acex.operations.execute", 2, "alice")
    assert run["request"] == {"commands": ["show version"]}


def test_ping_orders_a_run_of_typed_params(api):
    run = api.client.post(f"{OPS}/actions/ping", json=PING).json()

    assert run["type"] == "acex.operations.actions.ping"
    assert run["request"]["params"] == {
        "target": "10.0.0.1",
        "count": 5,
        "vrf": "MGMT",
        "source": None,
        "timeout": 2,
        "size": 1500,
    }
    assert [job.data["params"]["target"] for job in api.jobs.children(run["id"])] == ["10.0.0.1", "10.0.0.1"]


@pytest.mark.parametrize(
    "params", [{"target": "x", "count": 0}, {"target": "x", "count": 101}, {"target": "x", "size": 35}, {"target": ""}]
)
def test_ping_params_are_bounded(api, params):
    assert api.client.post(f"{OPS}/actions/ping", json={"node_ids": [1], "params": params}).status_code == 422


def test_nodes_whose_driver_cannot_run_it_make_no_run(api):
    response = api.client.post(f"{OPS}/actions/ping", json={**PING, "node_ids": [1, 3]})

    assert response.status_code == 422
    assert "old" in response.json()["detail"]
    assert api.jobs.list_jobs().items == []


def test_unknown_node_makes_no_run(api):
    assert api.client.post(f"{OPS}/execute", json={"node_ids": [9], "commands": ["show clock"]}).status_code == 404


def test_without_a_broker_answers_503(monkeypatch):
    api = _Api(monkeypatch, configured=False)

    assert api.client.post(f"{OPS}/execute", json={"node_ids": [1], "commands": ["show clock"]}).status_code == 503


def test_runs_are_listed_by_kind(api):
    execute = api.client.post(f"{OPS}/execute", json={"node_ids": [1], "commands": ["show clock"]}).json()
    ping = api.client.post(f"{OPS}/actions/ping", json=PING).json()

    def ids(kind=None):
        return [r["id"] for r in api.client.get(f"{OPS}/runs", params={"kind": kind} if kind else {}).json()["items"]]

    assert ids("execute") == [execute["id"]]
    assert ids("actions") == [ping["id"]]
    assert ids() == [ping["id"], execute["id"]]


def test_report_holds_each_nodes_response_by_hostname(api):
    run = api.client.post(f"{OPS}/actions/ping", json=PING).json()
    api.finish(run["id"], {1: {"sent": 5, "received": 5, "rtt_avg_ms": 2}, 2: "ping 10.0.0.1: % Unrecognized host"})

    report = api.client.get(f"{OPS}/runs/{run['id']}").json()

    assert report["state"] == "failed"
    assert [(r["hostname"], r["state"]) for r in report["responses"]] == [("sw-a", "failed"), ("sw-b", "succeeded")]
    assert report["responses"][0]["error"] == "ping 10.0.0.1: % Unrecognized host"
    assert report["responses"][1]["result"]["success"] is True


def test_report_downloads_as_csv_and_json(api):
    run = api.client.post(f"{OPS}/execute", json={"node_ids": [1, 2], "commands": ["a", "b"]}).json()
    outputs = {"outputs": [{"command": "a", "output": "A"}, {"command": "b", "output": "B"}]}
    api.finish(run["id"], {1: outputs, 2: "unreachable"})

    csv = api.client.get(f"{OPS}/runs/{run['id']}/report")
    assert csv.headers["content-disposition"] == f'attachment; filename="run-{run["id"]}.csv"'
    lines = csv.text.splitlines()
    assert lines[0] == "hostname,node_id,state,command,output,error,finished_at"
    assert [line.split(",")[:6] for line in lines[1:]] == [
        ["sw-a", "2", "failed", "", "", "unreachable"],
        ["sw-b", "1", "succeeded", "a", "A", ""],
        ["sw-b", "1", "succeeded", "b", "B", ""],
    ]

    json_report = api.client.get(f"{OPS}/runs/{run['id']}/report", params={"format": "json"})
    assert json_report.json()["responses"][1]["result"] == outputs


def test_unknown_run_answers_404(api):
    assert api.client.get(f"{OPS}/runs/99").status_code == 404


PATCH = {"node_ids": [1, 2], "paths": [" system.ntp.servers. ", "interfaces.Gi1"], "prune": True}
SCOPE = {"paths": ["system.ntp.servers", "interfaces.Gi1"], "prune": True}


def plan(api) -> int:
    """A finished plan: sw-b has a patch, sw-a is in sync."""
    run = api.client.post(f"{OPS}/patch/render", json=PATCH).json()
    api.finish(
        run["id"],
        {
            1: {"patch": "ntp server 10.0.0.2", "patch_hash": "h1", "changes": [{"op": "add", "path": "x"}]},
            2: {"patch": "", "patch_hash": None, "changes": []},
        },
    )
    return run["id"]


def test_patch_render_orders_a_run_of_its_scope(api):
    run = api.client.post(f"{OPS}/patch/render", json=PATCH).json()

    assert (run["type"], run["request"]) == ("acex.operations.patch.render", SCOPE)
    assert [job.data for job in api.jobs.children(run["id"])] == [{"node_id": 1, **SCOPE}, {"node_id": 2, **SCOPE}]


def test_patch_needs_a_driver_that_reads_and_writes_config(api):
    response = api.client.post(f"{OPS}/patch/render", json={**PATCH, "node_ids": [1, 3]})

    assert response.status_code == 422
    assert "old" in response.json()["detail"]


def test_patch_apply_sends_the_plans_scope_and_hash(api):
    plan_id = plan(api)

    run = api.client.post(f"{OPS}/patch/apply", json={"plan_id": plan_id, "node_ids": [1]}).json()

    assert (run["type"], run["request"]) == ("acex.operations.patch.apply", {"plan_id": plan_id})
    assert [job.data for job in api.jobs.children(run["id"])] == [
        {"node_id": 1, "plan_id": plan_id, "patch_hash": "h1", **SCOPE}
    ]


def test_patch_apply_refuses_nodes_the_plan_has_no_patch_for(api):
    plan_id = plan(api)

    response = api.client.post(f"{OPS}/patch/apply", json={"plan_id": plan_id, "node_ids": [1, 2]})

    assert response.status_code == 422
    assert response.json()["detail"] == f"Plan {plan_id} has no patch for: sw-a"


def test_patch_apply_needs_a_plan(api):
    ping = api.client.post(f"{OPS}/actions/ping", json=PING).json()

    for plan_id in (ping["id"], 99):
        assert api.client.post(f"{OPS}/patch/apply", json={"plan_id": plan_id, "node_ids": [1]}).status_code == 404


def test_patch_runs_are_listed_and_reported(api):
    plan_id = plan(api)

    assert [r["id"] for r in api.client.get(f"{OPS}/runs", params={"kind": "patch"}).json()["items"]] == [plan_id]
    lines = api.client.get(f"{OPS}/runs/{plan_id}/report").text.splitlines()
    assert lines[0] == "hostname,node_id,state,changes,patch,error,finished_at"
    assert [line.split(",")[:5] for line in lines[1:]] == [
        ["sw-a", "2", "succeeded", "0", ""],
        ["sw-b", "1", "succeeded", "1", "ntp server 10.0.0.2"],
    ]


def test_the_config_tree_names_what_a_path_walks(api):
    tree = api.client.get(f"{OPS}/patch/tree").json()
    system = next(c for c in tree["children"] if c["name"] == "system")
    ntp = next(c for c in system["children"] if c["name"] == "ntp")

    assert (tree["kind"], system["kind"]) == ("branch", "branch")
    assert [(c["name"], c["kind"]) for c in ntp["children"]] == [("config", "component"), ("servers", "collection")]
    servers = ntp["children"][1]
    assert ("address", "attribute") in [(c["name"], c["kind"]) for c in servers["children"]]


def test_an_empty_path_is_the_whole_tree(api):
    run = api.client.post(f"{OPS}/patch/render", json={"node_ids": [1], "paths": ["system", " "]}).json()

    assert run["request"] == {"paths": [], "prune": False}
