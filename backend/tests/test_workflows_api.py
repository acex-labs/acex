"""The workflows API: a workflow is saved as drawn and says what keeps it from running; a run starts only when
nothing does and every step on nodes has nodes that can run it. Workflow runs stay out of the bulk runs list."""

from types import SimpleNamespace

import pytest
from acex.api import auth
from acex.api.routers import operation_runs, workflows
from acex.jobs import JobManager
from acex.models.job import Job, JobState
from acex.operations.runs import OperationRuns
from acex.workflows.library import WorkflowLibrary
from acex.workflows.runs import WorkflowRuns
from acex_devkit.models.job import JobUpdate
from acex_devkit.models.ned import Capabilities
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

WF = "/api/v1/operations/workflows"


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
    """Node 1 acc-1 runs a driver with execute and ping; node 2 old one with neither."""

    NODES = {1: ("acc-1", "Full"), 2: ("old", "Bare")}

    async def get(self, id: str):
        if int(id) not in self.NODES:
            raise HTTPException(status_code=404, detail=f"Node instance {id} not found")
        hostname, ned = self.NODES[int(id)]
        return SimpleNamespace(
            id=int(id), asset=SimpleNamespace(ned_id=ned), logical_node=SimpleNamespace(hostname=hostname)
        )


class _Neds:
    CAPABILITIES = {
        "Full": Capabilities(operations=["execute"], actions=["ping"]),
        "Bare": Capabilities(operations=["get_config"]),
    }

    def get_driver_instance(self, name: str):
        return SimpleNamespace(capabilities=self.CAPABILITIES[name])


class _Api:
    def __init__(self, monkeypatch):
        db = _Db()
        self.db = db
        self.jobs = JobManager(db, _Producer())
        nodes = _Nodes()
        library = WorkflowLibrary(db)
        runs = WorkflowRuns(self.jobs, library, OperationRuns(self.jobs, nodes, _Neds()))
        monkeypatch.setattr(operation_runs, "NEDManager", _Neds)
        engine = SimpleNamespace(
            jobs=self.jobs,
            inventory=SimpleNamespace(node_instances=nodes),
            workflows=library,
            workflow_runs=runs,
        )
        app = FastAPI()
        app.include_router(workflows.create_router(engine))
        app.include_router(operation_runs.create_router(engine))
        app.dependency_overrides[auth.get_current_user] = lambda: {"sub": "alice"}
        self.client = TestClient(app)

    def workflow(self, step: dict, targets: list[int]) -> int:
        graph = {
            "nodes": [
                {"key": "start", "kind": "start"},
                {"key": "show", "step": step, "targets": targets},
                {"key": "end", "kind": "end"},
            ],
            "edges": [{"source": "start", "target": "show"}, {"source": "show", "target": "end"}],
        }
        response = self.client.post(WF, json={"name": "versions", "graph": graph})
        assert response.status_code == 201, response.text
        return response.json()["id"]


SHOW = {
    "type": "execute",
    "commands": ["show version"],
    "artifacts": [{"name": "version", "expression": "regex(result.output, 'Version (\\S+)')"}],
}


@pytest.fixture
def api(monkeypatch):
    return _Api(monkeypatch)


def test_a_workflow_is_saved_as_drawn_and_says_what_keeps_it_from_running(api):
    workflow = api.workflow({"type": "execute", "commands": ["show {nothing}"]}, [])
    check = api.client.get(f"{WF}/{workflow}").json()["check"]
    assert check["problems"] == {
        "show": ["Command 1: no artifact nothing in this workflow", "Choose the nodes it runs on"]
    }
    response = api.client.post(f"{WF}/{workflow}/runs", json={"mode": "dry_run"})
    assert response.status_code == 422 and "show: Choose the nodes it runs on" in response.json()["detail"]
    graph = {"nodes": [{"key": "start", "kind": "start"}, {"key": "end", "kind": "end"}], "edges": []}
    into_start = {**graph, "edges": [{"source": "end", "target": "start"}]}
    assert api.client.post(WF, json={"name": "w", "graph": into_start}).status_code == 422
    reserved = {
        **graph,
        "nodes": [
            *graph["nodes"],
            {"key": "a", "step": {"type": "compute", "artifacts": [{"name": "and", "expression": "1"}]}},
        ],
    }
    assert api.client.post(WF, json={"name": "w", "graph": reserved}).status_code == 422
    assert api.client.post(WF, json={"name": "empty"}).json()["check"]["problems"] == {"": ["Nothing follows start"]}


def test_the_builder_checks_a_graph_as_it_is_drawn(api):
    graph = {
        "nodes": [
            {"key": "start", "kind": "start"},
            {"key": "show", "step": SHOW, "targets": [1]},
            {"key": "check", "step": {"type": "assert", "checks": ["version == '17'"]}},
            {"key": "end", "kind": "end"},
        ],
        "edges": [{"source": "start", "target": "show"}, {"source": "show", "target": "check"}],
    }
    check = api.client.post(f"{WF}/check", json=graph).json()
    assert check["problems"] == {} and check["upstream"]["check"] == [
        {"name": "version", "step": "show", "per_node": True, "fields": []}
    ]


def test_a_run_needs_nodes_whose_driver_supports_the_step(api):
    response = api.client.post(f"{WF}/{api.workflow(SHOW, [1, 2])}/runs", json={"mode": "run"})
    assert response.status_code == 422 and "old" in response.json()["detail"]
    assert api.client.post(f"{WF}/{api.workflow(SHOW, [7])}/runs", json={}).status_code == 404


def test_a_run_through_the_api(api):
    workflow = api.workflow(SHOW, [1])
    started = api.client.post(f"{WF}/{workflow}/runs", json={"mode": "evaluate"})
    assert started.status_code == 202, started.text
    run = started.json()
    assert run["state"] == "running" and run["active"] == ["show"] and run["hostnames"] == {"1": "acc-1"}

    with Session(api.db.engine) as session:
        node_job = session.exec(select(Job).where(Job.subject_type == "node", Job.subject_id == 1)).one()
    api.jobs.update(node_job.id, JobUpdate(state=JobState.running), worker="w")
    result = {"result": {"output": "Version 17"}, "artifacts": {"version": "17"}}
    api.jobs.update(node_job.id, JobUpdate(state=JobState.succeeded, result=result), worker="w")

    assert api.client.get(f"{WF}/runs/{run['id']}").json()["state"] == "paused"
    artifacts = api.client.get(f"{WF}/runs/{run['id']}/artifacts", params={"names": ["version"]}).json()
    assert artifacts["artifacts"]["version"] == {"step": "show", "round": 1, "value": None, "nodes": {"acc-1": "17"}}
    assert api.client.delete(f"{WF}/runs/{run['id']}").status_code == 409
    assert api.client.post(f"{WF}/runs/{run['id']}/continue").json()["state"] == "succeeded"
    assert api.client.get(f"{WF}/runs", params={"workflow_id": workflow}).json()["total"] == 1
    assert api.client.get("/api/v1/operations/runs").json()["total"] == 0  # not a bulk run
    assert api.client.delete(f"{WF}/{workflow}").status_code == 204  # the run keeps its copy
    graph = api.client.get(f"{WF}/runs/{run['id']}").json()["graph"]
    assert graph["nodes"][1]["step"]["commands"] == ["show version"]
    assert api.client.delete(f"{WF}/runs/{run['id']}").status_code == 204
    assert api.client.get(f"{WF}/runs/{run['id']}").status_code == 404
