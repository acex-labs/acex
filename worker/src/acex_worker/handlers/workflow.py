"""Steps of a workflow run. Steps on nodes run one job per node, their templates rendered for that node from
earlier artifacts; the others run once. Every step then computes the artifacts it names, over its own `result`.

A dry run reaches no device: steps on nodes and probes report what they would do, the rest only check that the
artifacts they read are made somewhere in the workflow, and no artifacts are made.
"""

import json
import logging
from typing import Any

from acex_client import Acex
from acex_devkit.drivers import NetworkElementDriver, Session
from acex_devkit.models.actions import ActionParams, PingResult
from acex_devkit.models.job import JobResponse
from acex_devkit.models.operations import ExecuteData
from acex_devkit.models.workflows import (
    ArtifactValue,
    WorkflowArtifacts,
    WorkflowNodeJob,
    WorkflowNodeResult,
    WorkflowRunMode,
    WorkflowStepJob,
    WorkflowStepResult,
)
from acex_devkit.workflows import Expression, Template
from acex_devkit.workflows.expressions import Ref
from icmplib import ping

from .base_handler import Handler
from .execute import HandleExecute, NodeOperation

log = logging.getLogger("acex_worker")


class AssertionFailed(RuntimeError):
    pass


class RunArtifacts:
    """Artifacts as expressions read them, by name; `result`, when given, is the step's own result: per node
    by hostname, or one for the step."""

    def __init__(self, artifacts: WorkflowArtifacts, result: Any = None, host: str | None = None):
        self.artifacts = artifacts.artifacts
        self.result = result
        self.host = host

    def nodes(self, name: str) -> list[str]:
        if name == "result":
            return [self.host] if self.host is not None else []
        artifact = self.artifacts.get(name)
        return list(artifact.nodes) if artifact is not None and artifact.nodes is not None else []

    def get(self, name: str, node: str | None) -> Any:
        if name == "result":
            return self.result if node == self.host else None
        artifact = self.artifacts.get(name)
        if artifact is None:
            return None
        if artifact.nodes is None:
            return artifact.value if node is None else None
        return artifact.nodes.get(node) if node is not None else None


class StepContext:
    """What a step's job runs with: its run as it was when it started, and the artifacts it reads."""

    def __init__(self, client: Acex, ref: WorkflowStepJob):
        self.client = client
        self.ref = ref
        self.run = client.operations.workflows.get_run(run_id=ref.run_id)
        self.step = self.run.graph.node(ref.key).step
        self.dry_run = self.run.mode == WorkflowRunMode.dry_run
        self.producers = self.run.graph.producers()

    def check(self, refs: list[Ref]) -> list[str]:
        """The artifacts `refs` read, each of which must be made somewhere in the workflow; one not made yet
        just reads empty. `result` is the step's own."""
        names = sorted({ref.name for ref in refs} - {"result"})
        unknown = [name for name in names if name not in self.producers]
        if unknown:
            raise ValueError(f"No artifact {', '.join(unknown)} in this workflow")
        return names

    def artifacts(self, refs: list[Ref], result: Any = None, host: str | None = None) -> RunArtifacts:
        names = self.check(refs)
        fetched = self.client.operations.workflows.artifacts(run_id=self.ref.run_id, names=names) if names else None
        return RunArtifacts(fetched or WorkflowArtifacts(), result, host)

    def hostname(self, node_id: int) -> str:
        return self.run.hostnames.get(node_id, str(node_id))

    def definitions(self) -> list[tuple[str, Expression]]:
        """The step's artifacts by name; one without an expression is all of its result."""
        return [(a.name, Expression(a.expression.strip() or "result")) for a in self.step.artifacts]

    def node_artifacts(self, result: dict | None, host: str) -> dict[str, Any]:
        """The step's artifacts for one node, over that node's result."""
        definitions = self.definitions()
        if self.dry_run or not definitions:
            self.check([ref for _, expression in definitions for ref in expression.references()])
            return {}
        artifacts = self.artifacts([ref for _, e in definitions for ref in e.references()], result, host)
        return {name: expression.evaluate(artifacts, host) for name, expression in definitions}

    def once_artifacts(self, result: dict | None) -> dict[str, ArtifactValue]:
        """The step's artifacts over its one result: one value each, or per node when one reads earlier
        artifacts node by node."""
        definitions = self.definitions()
        if self.dry_run or not definitions:
            self.check([ref for _, expression in definitions for ref in expression.references()])
            return {}
        artifacts = self.artifacts([ref for _, e in definitions for ref in e.references()], result)
        values = {}
        for name, expression in definitions:
            nodes = expression.nodes(artifacts)
            if nodes is None:
                values[name] = ArtifactValue(value=expression.evaluate(artifacts))
            else:
                values[name] = ArtifactValue(nodes={node: expression.evaluate(artifacts, node) for node in nodes})
        return values


class Probe:
    """A ping from the worker itself, without privileges, reported as an action's ping is."""

    @staticmethod
    def ping(address: str, count: int, timeout: float) -> dict[str, Any]:
        host = ping(address, count=count, interval=0.5, timeout=timeout, privileged=False)
        rtt = host.packets_received > 0
        result = PingResult(
            sent=host.packets_sent,
            received=host.packets_received,
            rtt_min_ms=host.min_rtt if rtt else None,
            rtt_avg_ms=host.avg_rtt if rtt else None,
            rtt_max_ms=host.max_rtt if rtt else None,
        )
        return {**result.model_dump(mode="json"), "address": address}


class HandleWorkflowExecute(HandleExecute):
    """Raw commands on the job's node, rendered for that node. The result has each command's masked output, and
    all of it as `output`."""

    def handle(self, client: Acex, job: JobResponse) -> WorkflowNodeResult:
        data = WorkflowNodeJob.model_validate(job.data)
        context = StepContext(client, data)
        host = context.hostname(data.node_id)
        templates = [Template(command) for command in context.step.commands]
        artifacts = context.artifacts([ref for template in templates for ref in template.references()])
        commands = [template.render(artifacts, host).strip() for template in templates]
        if not all(commands):
            raise ValueError("A command rendered blank")
        if context.dry_run:
            return WorkflowNodeResult(result={"dry_run": True, "commands": commands})
        log.info(f"Job {job.id}: step {data.key} on node {data.node_id}")
        outcome = self.on_node(client, data.node_id, ExecuteData(node_id=data.node_id, commands=commands))
        result = {**outcome.model_dump(mode="json"), "output": "\n".join(o.output for o in outcome.outputs)}
        return WorkflowNodeResult(result=result, artifacts=context.node_artifacts(result, host))


class HandleWorkflowAction(NodeOperation):
    """An abstract action from the job's node, its text params rendered for that node; one that renders empty
    is left out."""

    PARAMS: dict[str, type[ActionParams]] = {params.action: params for params in ActionParams.__subclasses__()}

    def handle(self, client: Acex, job: JobResponse) -> WorkflowNodeResult:
        data = WorkflowNodeJob.model_validate(job.data)
        context = StepContext(client, data)
        step, host = context.step, context.hostname(data.node_id)
        if step.action not in self.PARAMS:
            raise ValueError(f"No action {step.action}")
        templates = {name: Template(value) for name, value in step.params.items() if isinstance(value, str)}
        artifacts = context.artifacts([ref for template in templates.values() for ref in template.references()])
        rendered = {name: template.render(artifacts, host) for name, template in templates.items()}
        params = self.PARAMS[step.action].model_validate(
            {**step.params, **{name: value or None for name, value in rendered.items()}}
        )
        if context.dry_run:
            return WorkflowNodeResult(result={"dry_run": True, "action": step.action, **params.model_dump(mode="json")})
        log.info(f"Job {job.id}: step {data.key} on node {data.node_id}")
        result = self.on_node(client, data.node_id, params).model_dump(mode="json")
        return WorkflowNodeResult(result=result, artifacts=context.node_artifacts(result, host))

    async def operate(self, driver: NetworkElementDriver, session: Session, params: ActionParams) -> Any:
        return await getattr(session, params.action)(params)


class HandleWorkflowProbe(Handler):
    """A ping from ACEX to the job's node: to its address when the step gives one, rendered for the node, or
    else to its primary management IP."""

    def handle(self, client: Acex, job: JobResponse) -> WorkflowNodeResult:
        data = WorkflowNodeJob.model_validate(job.data)
        context = StepContext(client, data)
        step, host = context.step, context.hostname(data.node_id)
        if step.address:
            template = Template(step.address)
            address = template.render(context.artifacts(template.references()), host).strip()
        else:
            address = self.management_ip(client, data.node_id)
        if not address:
            raise ValueError("The address rendered blank")
        if context.dry_run:
            return WorkflowNodeResult(result={"dry_run": True, "address": address})
        log.info(f"Job {job.id}: step {data.key} pings {address} for node {data.node_id}")
        result = Probe.ping(address, step.count, step.timeout)
        return WorkflowNodeResult(result=result, artifacts=context.node_artifacts(result, host))

    def management_ip(self, client: Acex, node_id: int) -> str:
        connections = client.inventory.management_connections.query(node_id=node_id).items
        connection = next((c for c in connections if c.primary), None)
        if connection is None or not connection.target_ip:
            raise ValueError(f"Node {node_id} has no primary management connection with an IP")
        return connection.target_ip


class HandleWorkflowProbeAddress(Handler):
    """A ping from ACEX to one address, rendered once."""

    def handle(self, client: Acex, job: JobResponse) -> WorkflowStepResult:
        context = StepContext(client, WorkflowStepJob.model_validate(job.data))
        step = context.step
        template = Template(step.address or "")
        address = template.render(context.artifacts(template.references())).strip()
        if not address:
            raise ValueError("The address rendered blank")
        if context.dry_run:
            return WorkflowStepResult(result={"dry_run": True, "address": address})
        result = Probe.ping(address, step.count, step.timeout)
        return WorkflowStepResult(result=result, artifacts=context.once_artifacts(result))


class HandleWorkflowCompute(Handler):
    """Only artifacts, from earlier ones."""

    def handle(self, client: Acex, job: JobResponse) -> WorkflowStepResult:
        context = StepContext(client, WorkflowStepJob.model_validate(job.data))
        return WorkflowStepResult(artifacts=context.once_artifacts(None))


class HandleWorkflowAssert(Handler):
    """Judges each check: one that reads per-node values must hold on every node. When the checks don't pass,
    as all or any of them, the job fails, which stops the run."""

    def handle(self, client: Acex, job: JobResponse) -> WorkflowStepResult:
        context = StepContext(client, WorkflowStepJob.model_validate(job.data))
        step = context.step
        checks = [Expression(check) for check in step.checks]
        refs = [ref for check in checks for ref in check.references()]
        if context.dry_run:
            context.check(refs)
            context.once_artifacts(None)
            return WorkflowStepResult(result={"dry_run": True})
        artifacts = context.artifacts(refs)
        results = [self.judge(check, artifacts) for check in checks]
        passed = [result["passed"] for result in results]
        if not (all(passed) if step.require == "all" else any(passed)):
            failed = "\n".join(self.why(result) for result in results if not result["passed"])
            raise AssertionFailed(f"{step.require.capitalize()} checks must pass. Failed:\n{failed}")
        result = {"passed": True, "checks": results}
        return WorkflowStepResult(result=result, artifacts=context.once_artifacts(result))

    def judge(self, check: Expression, artifacts: RunArtifacts) -> dict[str, Any]:
        """A check's outcome; a failed one with what it read, on the nodes it failed on."""
        nodes = check.nodes(artifacts)
        if nodes is None:
            passed = bool(check.evaluate(artifacts))
            inputs = {} if passed else check.inputs(artifacts)
            return {"check": check.text, "passed": passed, "failed_on": [], "inputs": inputs}
        failed_on = [node for node in nodes if not check.evaluate(artifacts, node)]
        inputs = check.inputs(artifacts, failed_on) if failed_on else {}
        return {"check": check.text, "passed": not failed_on, "failed_on": failed_on, "inputs": inputs}

    def why(self, result: dict[str, Any]) -> str:
        """A failed check, where it failed, and what it read there: a few nodes, then how many more."""
        failed_on = result["failed_on"]
        lines = [result["check"] + (f"  on {', '.join(failed_on[:10])}" if failed_on else "")]
        shown = list(result["inputs"].items())
        for node, values in shown[:5]:
            read = ", ".join(f"{name} = {self.short(value)}" for name, value in values.items())
            lines.append(f"  {node + ': ' if node else ''}{read}")
        more = len(failed_on) - min(len(shown), 5)
        if more > 0:
            lines.append(f"  and {more} more node{'s' if more > 1 else ''}")
        return "\n".join(lines)

    @staticmethod
    def short(value: Any) -> str:
        text = json.dumps(value, default=str)
        return text if len(text) <= 120 else f"{text[:117]}..."


class HandleWorkflowCondition(Handler):
    """Gives one true or false for the run to choose its way by. In a dry run it gives neither, so both ways
    are shown."""

    def handle(self, client: Acex, job: JobResponse) -> WorkflowStepResult:
        context = StepContext(client, WorkflowStepJob.model_validate(job.data))
        check = Expression(context.step.check)
        if context.dry_run:
            context.check(check.references())
            context.once_artifacts(None)
            return WorkflowStepResult(result={"dry_run": True})
        artifacts = context.artifacts(check.references())
        if check.nodes(artifacts) is not None:
            names = ", ".join(check.names)
            raise ValueError(f"The condition reads {names} per node: use all(), any(), percent() or count()")
        result = {"value": bool(check.evaluate(artifacts)), "inputs": check.inputs(artifacts)}
        return WorkflowStepResult(result=result, artifacts=context.once_artifacts(result))
