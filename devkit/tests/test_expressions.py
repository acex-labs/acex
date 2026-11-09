"""The workflow expression language reads artifacts and computes values, and refuses anything else."""

import pytest
from acex_devkit.workflows import Expression, ExpressionError, Template

SHOW_VER = "Cisco IOS XE Software, Version 17.09.04a\nuptime is 3 weeks\n"
INT_BRIEF = (
    "Interface          IP-Address  OK? Method Status   Protocol\n"
    "Gi1/0/1            unassigned  YES unset  up       up\n"
    "Gi1/0/2            unassigned  YES unset  down     down\n"
    "Gi1/0/3            unassigned  YES unset  down     down\n"
)


class Artifacts:
    """Two access switches pinged and asked for their version, a core's interfaces, and one value found once."""

    DATA = {
        "ping": {
            "acc-1": {"success_rate": 100.0, "success": True, "rtt_avg_ms": 2.0},
            "acc-2": {"success_rate": 60.0, "success": False, "rtt_avg_ms": None},
        },
        "show_ver": {"acc-1": SHOW_VER, "acc-2": SHOW_VER.replace("17.09.04a", "16.12.1")},
        "int_brief": {"core-1": INT_BRIEF},
        "find": {None: {"iface": "Gi1/0/2", "lines": ["a", "b"]}},
        "count": {None: 3},
    }

    def nodes(self, name):
        return [node for node in self.DATA.get(name, {}) if node is not None]

    def get(self, name, node):
        return self.DATA.get(name, {}).get(node)


A = Artifacts()


def per_node(text):
    expression = Expression(text)
    return {node: expression.evaluate(A, node) for node in expression.nodes(A)}


def test_a_nodes_own_values_are_checked_node_by_node():
    assert per_node("ping.success_rate >= 80") == {"acc-1": True, "acc-2": False}
    assert per_node('regex(show_ver, "Version (\\S+)") == "17.09.04a"') == {"acc-1": True, "acc-2": False}


def test_aggregates_read_every_node():
    assert Expression("all(ping.success)").evaluate(A) is False
    assert Expression("any(ping.success)").evaluate(A) is True
    assert Expression("percent(ping.success_rate >= 80)").evaluate(A) == 50.0
    assert Expression("count(ping.success) == 1").evaluate(A) is True
    assert Expression("percent(ping.success) >= 95").nodes(A) is None  # evaluated once


def test_a_named_node_and_a_single_value():
    assert Expression("count(int_brief[core-1], ' down ') == 2").evaluate(A) is True
    assert Expression('int_brief["core-1"] contains "Gi1/0/3"').evaluate(A) is True
    assert Expression("find.iface").evaluate(A) == "Gi1/0/2"
    assert Expression("find.lines.1").evaluate(A) == "b"
    assert Expression("find.iface").nodes(A) is None  # a single value is read once


def test_a_name_is_a_function_only_when_called():
    assert Expression("count == 3").evaluate(A) is True
    assert Expression("count(find.lines, '.') == 2").evaluate(A) is True
    assert Expression("ping.success and find").names == ["ping", "find"]


def test_text_functions():
    text = "int_brief[core-1]"
    assert Expression(f"lines({text}, 'down')").evaluate(A) == [INT_BRIEF.splitlines()[2], INT_BRIEF.splitlines()[3]]
    assert Expression(f"column(lines({text}, ' down '), 1)").evaluate(A) == ["Gi1/0/2", "Gi1/0/3"]
    assert Expression(f"column({text}, 2, 'YES')").evaluate(A) == [
        "unset  up       up",
        "unset  down     down",
        "unset  down     down",
    ]
    assert Expression(f"{text} matches 'Gi1/0/[23] .* down'").evaluate(A) is True
    assert Expression(f"column({text}, 1) contains 'Gi1/0/1'").evaluate(A) is True


def test_patterns_keep_their_escapes():
    assert Expression(r"regex('Version 17.9', 'Version (\d+)')").evaluate(A) == "17"
    assert Expression(r"'say \"hi\"' contains 'hi'").evaluate(A) is True


def test_values_compare_sensibly():
    assert Expression("'5' == 5").evaluate(A) is True
    assert Expression("'10' > 9").evaluate(A) is True
    assert Expression("'abc' < 3").evaluate(A) is False  # text and number don't order
    assert Expression("not (1 > 2) and (true or false)").evaluate(A) is True
    assert Expression("null == never_made.x").evaluate(A) is True  # an artifact not made yet reads as nothing
    assert per_node("ping.rtt_avg_ms < 10") == {"acc-1": True, "acc-2": False}


def test_a_per_node_artifact_needs_a_node_or_an_aggregate_outside_per_node_evaluation():
    with pytest.raises(ExpressionError, match=r"ping\[host\]"):
        Expression("ping.success").evaluate(A)


@pytest.mark.parametrize(
    "text",
    [
        "__import__('os').system('id')",
        "ping.__class__",  # a field name is only ever a key in the artifact
        "open('/etc/passwd')",
        "lambda: 1",
        "[x for x in ping]",
        "1 + 1",
        "regex(show_ver)",
        "show_ver matches '(unclosed'",
        "contains == 1",
        "",
    ],
)
def test_anything_but_the_language_is_refused(text):
    if text == "ping.__class__":
        assert Expression(text).evaluate(A, "acc-1") is None
        return
    with pytest.raises(ExpressionError):
        Expression(text)


def test_long_expressions_are_refused():
    with pytest.raises(ExpressionError, match="longer than"):
        Expression("1 == " + "1" * Expression.MAX_LENGTH)


def test_templates_render_per_node():
    template = Template("interface {find.iface}\n description {ping.success_rate}% {{ok}}")
    assert template.names == ["find", "ping"]
    assert template.render(A, "acc-2") == "interface Gi1/0/2\n description 60.0% {ok}"
    assert Template("{find.lines}").render(A) == "a\nb"
    assert Template("x{never_made}y").render(A) == "xy"


def test_an_object_is_not_text_and_not_true_or_false():
    """As in a run where a whole execute result went to regex() and all(): both are refused, naming its fields."""

    class Whole:
        RESULT = {"output": "Cisco IOS XE Software, Version 17.09.04a\nCisco IOS", "outputs": []}

        def nodes(self, name):
            return ["lab-1"]

        def get(self, name, node):
            return self.RESULT if node == "lab-1" else None

    whole = Whole()
    with pytest.raises(ExpressionError, match=r"regex\(\) needs text, but got an object with fields output, outputs"):
        Expression('regex(version_out, "Version (\\S+)")').evaluate(whole, "lab-1")
    with pytest.raises(ExpressionError, match=r"all\(\) needs true or false per node, but got an object .* on lab-1"):
        Expression('all(version_out) == "17.09.04a"').evaluate(whole)
    with pytest.raises(ExpressionError, match="needs text"):
        Template("show {version_out}").render(whole, "lab-1")
    assert Expression('regex(version_out.output, "Version (\\S+)")').evaluate(whole, "lab-1") == "17.09.04a"


def test_an_expression_shows_what_it_read():
    assert Expression("percent(ping.success) >= 95 and find.iface == 'x'").inputs(A) == {
        "acc-1": {"ping.success": True, "find.iface": "Gi1/0/2"},
        "acc-2": {"ping.success": False, "find.iface": "Gi1/0/2"},
    }
    assert Expression("find.iface == 'x'").inputs(A) == {"": {"find.iface": "Gi1/0/2"}}
    assert Expression("ping.rtt_avg_ms < 1").inputs(A, ["acc-2"]) == {"acc-2": {"ping.rtt_avg_ms": None}}
