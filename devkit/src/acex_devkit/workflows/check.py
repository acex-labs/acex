"""What keeps a workflow from running, and what in it is worth a second look.

A workflow is saved as it is drawn, so a step may be unfinished: its problems say what is missing, and a run
won't start while there are any. Warnings don't stop a run: a loop with no way out or no wait, or a step that
reads an artifact made by a step that doesn't run before it.
"""

from acex_devkit.models.actions import ActionParams, PingResult
from acex_devkit.models.workflows import GraphNode, UpstreamArtifact, WorkflowCheck, WorkflowGraph
from acex_devkit.workflows.expressions import Expression, ExpressionError, Template


class WorkflowChecker:
    #: The abstract actions an action step can run, by name.
    ACTIONS: dict[str, type[ActionParams]] = {params.action: params for params in ActionParams.__subclasses__()}
    _PING = [*PingResult.model_fields, *PingResult.model_computed_fields]
    #: The fields of each step type's result, for an artifact that is all of it. An action's are its action's.
    RESULT_FIELDS = {
        "execute": ["output", "outputs"],
        "action": _PING,
        "probe": [*_PING, "address"],
        "assert": ["passed", "checks"],
        "condition": ["value"],
    }

    def __init__(self, graph: WorkflowGraph):
        self.graph = graph
        self.steps = [node for node in graph.nodes if node.kind == "step"]
        self.producers = graph.producers()
        self.result = WorkflowCheck()

    def check(self) -> WorkflowCheck:
        start = next(node.key for node in self.graph.nodes if node.kind == "start")
        if not self.graph.outgoing(start):
            self.problem("", "Nothing follows start")
        for node in self.steps:
            self.result.upstream[node.key] = self.upstream(node.key)
            getattr(self, f"check_{node.step.type}")(node)
            self.check_artifacts(node)
        self.check_loops()
        return self.result

    def problem(self, key: str, text: str) -> None:
        self.result.problems.setdefault(key, []).append(text)

    def warning(self, key: str, text: str) -> None:
        self.result.warnings.setdefault(key, []).append(text)

    # ------------------------------------------------------------------ steps

    def check_execute(self, node: GraphNode) -> None:
        if not node.step.commands:
            self.problem(node.key, "Add a command")
        for number, command in enumerate(node.step.commands, 1):
            self.template(node, command, f"Command {number}")
        self.check_targets(node)

    def check_action(self, node: GraphNode) -> None:
        step = node.step
        params = self.ACTIONS.get(step.action)
        if params is None:
            self.problem(node.key, f"No action {step.action}")
        else:
            for name, field in params.model_fields.items():
                if field.is_required() and step.params.get(name) in (None, ""):
                    self.problem(node.key, f"Set {name}")
        for name, value in step.params.items():
            if isinstance(value, str):
                self.template(node, value, name.capitalize())
        self.check_targets(node)

    def check_probe(self, node: GraphNode) -> None:
        if not node.targets and not node.step.address:
            self.problem(node.key, "Choose nodes to ping, or an address")
        if node.step.address:
            self.template(node, node.step.address, "Address")

    def check_compute(self, node: GraphNode) -> None:
        if not node.step.artifacts:
            self.problem(node.key, "Name at least one artifact to compute")

    def check_assert(self, node: GraphNode) -> None:
        if not node.step.checks:
            self.problem(node.key, "Add a check")
        for number, check in enumerate(node.step.checks, 1):
            self.expression(node, check, f"Check {number}")

    def check_condition(self, node: GraphNode) -> None:
        expression = self.expression(node, node.step.check, "Condition")
        if expression is not None:
            per_node = [name for name in expression.names if self.per_node(name)]
            if per_node:
                names = ", ".join(per_node)
                self.problem(node.key, f"Reads {names} per node: use all(), any(), percent() or count() for one answer")
        for side in ("true", "false"):
            if not self.graph.outgoing(node.key, side):
                self.warning(node.key, f"Nothing follows its {side} side: there the run ends")

    def check_wait(self, node: GraphNode) -> None:
        pass

    def check_targets(self, node: GraphNode) -> None:
        if not node.targets:
            self.problem(node.key, "Choose the nodes it runs on")

    def check_artifacts(self, node: GraphNode) -> None:
        if node.step.artifacts and node.step.type == "wait":
            self.problem(node.key, "A wait leaves no artifacts")
            return
        for artifact in node.step.artifacts:
            if not artifact.expression.strip() and node.step.type != "compute":
                continue  # all of the step's result
            self.expression(node, artifact.expression, f"Artifact {artifact.name}", own=node.step.type != "compute")

    # ------------------------------------------------------------------ expressions

    def expression(self, node: GraphNode, text: str, label: str, *, own: bool = False) -> Expression | None:
        """Parse an expression of the step at `node`, reporting what's wrong with it. `own` lets it read the
        step's own `result`, as its artifacts do."""
        if not text.strip():
            self.problem(node.key, f"{label} is empty")
            return None
        try:
            expression = Expression(text)
        except ExpressionError as exc:
            self.problem(node.key, f"{label}: {exc}")
            return None
        self.check_names(node, [ref.name for ref in expression.references()], label, own)
        return expression

    def template(self, node: GraphNode, text: str, label: str) -> None:
        try:
            template = Template(text)
        except ExpressionError as exc:
            self.problem(node.key, f"{label}: {exc}")
            return
        self.check_names(node, [ref.name for ref in template.references()], label, own=False)

    def check_names(self, node: GraphNode, names: list[str], label: str, own: bool) -> None:
        before = {artifact.name for artifact in self.result.upstream[node.key]}
        for name in dict.fromkeys(names):
            if name == "result":
                if not own:
                    self.problem(node.key, f"{label}: result is only read in the step's own artifacts")
            elif name not in self.producers:
                self.problem(node.key, f"{label}: no artifact {name} in this workflow")
            elif name not in before and self.producers[name] != node.key:
                self.warning(node.key, f"{label}: {name} is made by {self.producers[name]}, which doesn't run before")

    def per_node(self, name: str, seen: frozenset[str] = frozenset()) -> bool:
        """Whether an artifact has a value per node: one made by a step on nodes, or computed from such
        without an aggregate."""
        key = self.producers.get(name)
        if key is None or name in seen:
            return False
        node = self.graph.node(key)
        if node.on_nodes:
            return True
        text = next(a.expression for a in node.step.artifacts if a.name == name)
        try:
            names = Expression(text.strip() or "result").names
        except ExpressionError:
            return False
        return any(self.per_node(other, seen | {name}) for other in names if other != "result")

    # ------------------------------------------------------------------ graph

    def upstream(self, key: str) -> list[UpstreamArtifact]:
        """The artifacts of the steps that can run before `key`: every step it can be reached from."""
        seen, todo = set(), list(self.graph.incoming(key))
        while todo:
            source = todo.pop()
            if source not in seen:
                seen.add(source)
                todo += self.graph.incoming(source)
        return [
            UpstreamArtifact(
                name=artifact.name,
                step=node.key,
                per_node=self.per_node(artifact.name),
                fields=[] if artifact.expression.strip() else self.RESULT_FIELDS.get(node.step.type, []),
            )
            for node in self.steps
            if node.key in seen
            for artifact in node.step.artifacts
        ]

    def check_loops(self) -> None:
        """Warn on each step of a loop that has no way out, or goes round without waiting."""
        for loop in self.loops():
            kinds = {key: self.graph.node(key).step.type for key in loop}
            exits = [
                key
                for key in loop
                if kinds[key] == "condition" and any(target not in loop for target in self.graph.outgoing(key))
            ]
            for key in sorted(loop):
                if not exits:
                    self.warning(key, "In a loop with no way out: add a condition with an edge out of the loop")
                if "wait" not in kinds.values():
                    self.warning(key, "In a loop with no wait: it goes round as fast as it can")

    def loops(self) -> list[set[str]]:
        """The graph's loops: its strongly connected parts of more than one step, or a step leading to itself
        (Tarjan's algorithm)."""
        index: dict[str, int] = {}
        low: dict[str, int] = {}
        stack: list[str] = []
        loops: list[set[str]] = []

        for root in (node.key for node in self.steps):
            if root in index:
                continue
            # Iteratively, so a long chain of steps can't exhaust the recursion limit.
            work = [(root, iter(self.graph.outgoing(root)))]
            index[root] = low[root] = len(index)
            stack.append(root)
            while work:
                key, targets = work[-1]
                target = next(targets, None)
                if target is not None:
                    if target not in index:
                        index[target] = low[target] = len(index)
                        stack.append(target)
                        work.append((target, iter(self.graph.outgoing(target))))
                    elif target in stack:
                        low[key] = min(low[key], index[target])
                    continue
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[key])
                if low[key] == index[key]:
                    part = set()
                    while True:
                        member = stack.pop()
                        part.add(member)
                        if member == key:
                            break
                    if len(part) > 1 or key in self.graph.outgoing(key):
                        loops.append(part)
        return loops
