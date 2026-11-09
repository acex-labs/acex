from acex_devkit.models.workflows import WorkflowRunData, WorkflowRunMode


class RoundLimit(RuntimeError):
    """A step would run more times than its workflow allows."""


class Walk:
    """How a run moves through its graph: which steps start when one finishes. Works on the run's data only;
    whoever holds the run starts the steps it returns.

    A finished step fires each of its edges. A step starts once an edge into it has fired and each of its
    other edges in has too, unless that edge's step can no longer run: neither active, pending, nor reachable
    from one without passing through the step itself. So a join waits for its branches, and a step inside a
    loop starts the first time without waiting on the edge that loops back. A condition fires only the edges
    of the side it took; one that took none, as in a dry run, fires both.
    """

    def __init__(self, data: WorkflowRunData):
        self.data = data
        self.graph = data.graph

    def begin(self) -> list[str]:
        start = next(node.key for node in self.graph.nodes if node.kind == "start")
        self.fire(start)
        return self.ready()

    def finish(self, key: str, branch: str | None = None) -> list[str]:
        """A step finished well; a condition says which side it took. In evaluate mode its edges wait for
        `resume`."""
        self.data.active.remove(key)
        if branch is None:
            self.data.branches.pop(key, None)
        else:
            self.data.branches[key] = branch
        if self.data.mode == WorkflowRunMode.evaluate:
            self.data.pending.append(key)
            return []
        self.fire(key)
        return self.ready()

    def resume(self) -> list[str]:
        """Fire the edges of the steps that finished while paused."""
        pending, self.data.pending = self.data.pending, []
        for key in pending:
            self.fire(key)
        return self.ready()

    def fire(self, source: str) -> None:
        for target in self.graph.outgoing(source, self.data.branches.get(source)):
            if self.graph.node(target).kind == "end":
                continue
            fired = self.data.fired.setdefault(target, [])
            if source not in fired:
                fired.append(source)

    def ready(self) -> list[str]:
        """Start the steps whose edges in have all fired or can no longer fire. Raises RoundLimit for a step
        that would run once too often."""
        started = []
        for key in list(self.data.fired):
            if key in self.data.active:
                continue
            # A dry run shows each step once, rather than going round a loop for ever.
            if self.data.mode == WorkflowRunMode.dry_run and self.data.rounds.get(key):
                del self.data.fired[key]
                continue
            fired = self.data.fired[key]
            if any(source not in fired and self.can_fire(source, key) for source in self.graph.incoming(key)):
                continue
            del self.data.fired[key]
            if self.data.rounds.get(key, 0) >= self.data.max_rounds:
                raise RoundLimit(f"Step {key} ran {self.data.max_rounds} times, as many as the workflow allows")
            self.data.rounds[key] = self.data.rounds.get(key, 0) + 1
            self.data.active.append(key)
            started.append(key)
        return started

    def can_fire(self, source: str, target: str) -> bool:
        """Whether `source` may still fire into `target`: it is active or pending, or one of those reaches it
        without passing through `target`."""
        seen = set(self.data.active) | set(self.data.pending)
        todo = list(seen)
        while todo:
            for nxt in self.graph.outgoing(todo.pop()):
                if nxt != target and nxt not in seen:
                    seen.add(nxt)
                    todo.append(nxt)
        return source in seen

    @property
    def done(self) -> bool:
        return not self.data.active and not self.data.pending
