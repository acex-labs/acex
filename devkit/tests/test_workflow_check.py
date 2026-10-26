"""A workflow is saved as drawn; its check says what keeps it from running and what deserves a second look."""

import pytest
from acex_devkit.models.workflows import WorkflowGraph
from acex_devkit.workflows.check import WorkflowChecker
from pydantic import ValidationError


def graph(steps: dict[str, dict], edges: str, targets: dict[str, list[int]] | None = None) -> WorkflowGraph:
    """`steps` maps keys to step configs; `edges` reads "start>a a>b:true b>end"."""
    targets = targets or {}
    nodes = [{"key": "start", "kind": "start"}, {"key": "end", "kind": "end"}]
    nodes += [{"key": key, "step": step, "targets": targets.get(key, [1])} for key, step in steps.items()]
    links = []
    for edge in edges.split():
        ends, _, branch = edge.partition(":")
        source, target = ends.split(">")
        links.append({"source": source, "target": target, "branch": branch or None})
    return WorkflowGraph.model_validate({"nodes": nodes, "edges": links})


def check(*args, **kwargs):
    return WorkflowChecker(graph(*args, **kwargs)).check()


SHOW = {
    "type": "execute",
    "commands": ["show version"],
    "artifacts": [{"name": "version", "expression": "regex(result.output, 'Version (\\\\S+)')"}],
}
PING = {
    "type": "action",
    "params": {"target": "10.0.0.1"},
    "artifacts": [{"name": "reachable", "expression": "result.success"}],
}


def test_an_unfinished_step_has_problems():
    result = check(
        {
            "a": {"type": "execute"},
            "b": {"type": "action", "params": {}},
            "c": {"type": "compute"},
            "d": {"type": "condition"},
            "e": {"type": "probe"},
        },
        "a>end",
        targets={"a": [], "e": []},
    )
    assert result.problems == {
        "": ["Nothing follows start"],
        "a": ["Add a command", "Choose the nodes it runs on"],
        "b": ["Set target"],
        "c": ["Name at least one artifact to compute"],
        "d": ["Condition is empty"],
        "e": ["Choose nodes to ping, or an address"],
    }


def test_a_finished_workflow_has_none_and_knows_what_each_step_can_read():
    result = check(
        {
            "show": SHOW,
            "ping": PING,
            "ok": {"type": "assert", "checks": ["percent(reachable) >= 95", "version == '17.9'"]},
        },
        "start>show show>ping ping>ok ok>end",
    )
    assert result.problems == {} and result.warnings == {}
    assert [(a.name, a.step, a.per_node) for a in result.upstream["ok"]] == [
        ("version", "show", True),
        ("reachable", "ping", True),
    ]
    assert result.upstream["show"] == []


def test_names_must_be_made_somewhere_and_result_is_a_steps_own():
    result = check(
        {
            "show": {"type": "execute", "commands": ["show {iface}", "show {result.x}"]},
            "find": {"type": "compute", "artifacts": [{"name": "iface", "expression": "result.output"}]},
        },
        "start>show show>find",
    )
    assert result.problems["show"] == [
        "Command 2: result is only read in the step's own artifacts",
    ]
    assert result.warnings["show"] == ["Command 1: iface is made by find, which doesn't run before"]
    assert result.problems["find"] == ["Artifact iface: result is only read in the step's own artifacts"]
    assert check({"a": {"type": "assert", "checks": ["typo > 1"]}}, "start>a").problems["a"] == [
        "Check 1: no artifact typo in this workflow"
    ]


def test_a_condition_gives_one_answer():
    steps = {"ping": PING, "up": {"type": "condition", "check": "reachable"}}
    result = check(steps, "start>ping ping>up up>end:true up>ping:false")
    assert result.problems["up"] == ["Reads reachable per node: use all(), any(), percent() or count() for one answer"]
    steps["up"]["check"] = "all(reachable)"
    # A computed artifact read node by node is per node too.
    steps["all_up"] = {"type": "compute", "artifacts": [{"name": "fine", "expression": "reachable and true"}]}
    steps["up"]["check"] = "fine"
    result = check(steps, "start>ping ping>all_up all_up>up up>end:true up>ping:false")
    assert result.problems["up"][0].startswith("Reads fine per node")


def test_loops_without_a_way_out_or_a_wait_are_warned_about():
    steps = {"ping": PING, "again": {"type": "compute", "artifacts": [{"name": "n", "expression": "1"}]}}
    warnings = check(steps, "start>ping ping>again again>ping").warnings
    assert warnings["ping"] == [
        "In a loop with no way out: add a condition with an edge out of the loop",
        "In a loop with no wait: it goes round as fast as it can",
    ]
    steps = {
        "ping": PING,
        "up": {"type": "condition", "check": "all(reachable)"},
        "pause": {"type": "wait", "seconds": 10},
    }
    assert check(steps, "start>ping ping>up up>end:true up>pause:false pause>ping").warnings == {}


def test_the_graph_refuses_what_can_never_make_sense():
    with pytest.raises(ValidationError, match="artifact names must be unique: reachable"):
        graph({"a": PING, "b": PING}, "start>a")
    with pytest.raises(ValidationError, match="only edges from a condition take a side"):
        graph({"a": PING}, "start>a a>end:true")
    with pytest.raises(ValidationError, match="only edges from a condition take a side"):
        graph({"c": {"type": "condition", "check": "true"}}, "start>c c>end")
    with pytest.raises(ValidationError, match="word of the expression language"):
        graph({"a": {"type": "compute", "artifacts": [{"name": "result", "expression": "1"}]}}, "start>a")


def test_an_artifact_without_an_expression_is_all_of_the_steps_result():
    ping = {"type": "action", "params": {"target": "10.0.0.1"}, "artifacts": [{"name": "ping_google"}]}
    steps = {
        "ping": ping,
        "ok": {"type": "assert", "checks": ["ping_google.success_rate >= 80"]},
        "c": {"type": "compute", "artifacts": [{"name": "nothing", "expression": " "}]},
    }
    result = check(steps, "start>ping ping>ok ok>c")
    assert result.problems == {"c": ["Artifact nothing is empty"]}
    (upstream,) = result.upstream["ok"]
    assert upstream.name == "ping_google" and upstream.per_node and "success_rate" in upstream.fields
