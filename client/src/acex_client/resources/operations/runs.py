from typing import Literal

from acex_devkit.models.actions import PingParams
from acex_devkit.models.operations import ActionRequest, ExecuteRequest, Run, RunReport

from acex_client.resources.base import ActionMixin, ListMixin, Resource, action


class Execute(Resource, ActionMixin):
    """Raw commands — `/operations/execute`.

    `client.operations.execute([1, 2], ["show version"])` orders a run and returns it; read each node's
    masked output with `client.operations.runs.get(run.id)` once workers have run it.
    """

    path = "/operations"
    response_model = Run  # type: ignore
    list_model = Run  # type: ignore
    create_model = None  # type: ignore
    update_model = None  # type: ignore

    @action("POST", "execute")
    def run(self, payload: ExecuteRequest) -> Run: ...

    def __call__(self, node_ids: list[int], commands: list[str]) -> Run:
        return self.run(payload=ExecuteRequest(node_ids=node_ids, commands=commands))


class Actions(Resource, ActionMixin):
    """Abstract actions — `/operations/actions/<action>`: the same params and result for every vendor.

    `client.operations.actions.ping([1, 2], target="10.0.0.1", count=5)` orders a run and returns it.
    """

    path = "/operations/actions"
    response_model = Run  # type: ignore
    list_model = Run  # type: ignore
    create_model = None  # type: ignore
    update_model = None  # type: ignore

    @action("POST", "ping")
    def run_ping(self, payload: ActionRequest[PingParams]) -> Run: ...

    def ping(self, node_ids: list[int], **params) -> Run:
        return self.run_ping(payload=ActionRequest[PingParams](node_ids=node_ids, params=PingParams(**params)))


class Runs(Resource, ListMixin, ActionMixin):
    """Runs — `/operations/runs`. `query(kind="execute"|"actions")` lists runs newest first; `get()` one
    run with each node's response, sorted by hostname."""

    path = "/operations/runs"
    response_model = RunReport  # type: ignore
    list_model = Run  # type: ignore
    create_model = None  # type: ignore
    update_model = None  # type: ignore

    @action("GET", "{run_id}")
    def get(self, run_id: int) -> RunReport: ...

    def report(self, run_id: int, format: Literal["csv", "json"] = "csv") -> bytes:
        """The run's report as a file's contents."""
        return self.rest.download(f"{self.path}/{run_id}/report", params={"format": format})
