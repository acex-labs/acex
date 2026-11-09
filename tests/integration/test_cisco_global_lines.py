"""The Cisco IOS codec starts a configuration with the spanning tree mode and writes the clock timezone."""

import pytest
from acex.configuration.components.spanning_tree import SpanningTreeGlobal
from acex.configuration.components.system.clock import Clock as ClockComponent
from acex.configuration.configuration import Configuration
from acex_devkit.models.composed_configuration import Clock, ClockConfig, ComposedConfiguration, System, SystemConfig
from acex_devkit.models.spanning_tree import SpanningTree, SpanningTreeGlobalAttributes
from acex_driver_cisco_ioscli.codec import CiscoIOSCodec

CODEC = CiscoIOSCodec()
STARTS_WITH = ["spanning-tree mode rapid-pvst", "spanning-tree extend system-id"]


def spanning_tree(mode: str) -> SpanningTree:
    """The collection the model types `stp.config` as, which is how a configuration read back from JSON holds it."""
    return SpanningTree(config={"core": SpanningTreeGlobalAttributes(mode=mode)})


def composed(*components) -> ComposedConfiguration:
    """What the backend hands a driver: a configuration composed from components, where `stp.config` is the
    one `SpanningTreeGlobal` itself."""
    configuration = Configuration("lab")
    for component in components:
        configuration.add(component)
    return configuration.as_model()


def clock(timezone: str | None) -> System:
    return System(clock=Clock(config=ClockConfig(timezone=timezone)))


def render(config: ComposedConfiguration):
    return CODEC.render(config, None)


def test_an_empty_configuration_is_just_the_spanning_tree_lines():
    assert render(ComposedConfiguration()).payload.splitlines() == STARTS_WITH


def test_rapid_pvst_is_the_mode_when_none_is_declared():
    config = ComposedConfiguration(system=System(config=SystemConfig(hostname="sw1")))

    lines = render(config).payload.splitlines()

    assert lines[:3] == [*STARTS_WITH, "!"]
    assert "hostname sw1" in lines


@pytest.mark.parametrize(
    ("declared", "written"),
    [
        ("rapid-pvst", "rapid-pvst"),
        ("RAPID_PVST", "rapid-pvst"),
        ("pvst", "pvst"),
        ("mst", "mst"),
        ("MSTP", "mst"),
    ],
)
def test_a_declared_mode_is_written_as_the_ios_keyword(declared, written):
    lines = render(ComposedConfiguration(stp=spanning_tree(declared))).payload.splitlines()

    assert lines == [f"spanning-tree mode {written}", "spanning-tree extend system-id"]


@pytest.mark.parametrize("declared", ["rstp", "something else"])
def test_a_mode_ios_has_no_keyword_for_leaves_the_default(declared):
    lines = render(ComposedConfiguration(stp=spanning_tree(declared))).payload.splitlines()

    assert lines == STARTS_WITH


@pytest.mark.parametrize(("declared", "written"), [("mst", "mst"), ("rapid-pvst", "rapid-pvst"), ("pvst", "pvst")])
def test_a_configuration_composed_from_components_gets_its_declared_mode(declared, written):
    config = composed(
        SpanningTreeGlobal(mode=declared, bpdu_guard=True, portfast=True), ClockComponent(timezone="cet 1")
    )

    result = render(config)
    lines = result.payload.splitlines()

    assert lines[:3] == [f"spanning-tree mode {written}", "spanning-tree extend system-id", "!"]
    assert "clock timezone CET 1" in lines
    assert {tuple(span.path): (span.start, span.end) for span in result.metadata.spans}[("stp", "config")] == (1, 2)


def test_a_composed_configuration_without_a_spanning_tree_component_gets_the_default():
    lines = render(composed(ClockComponent(timezone="cet 1"))).payload.splitlines()

    assert lines[:2] == STARTS_WITH


def test_a_spanning_tree_component_without_a_mode_leaves_the_default():
    lines = render(composed(SpanningTreeGlobal(bpdu_guard=True))).payload.splitlines()

    assert lines == STARTS_WITH


def test_spans_follow_the_lines_they_describe():
    config = ComposedConfiguration(system=System(config=SystemConfig(hostname="sw1")), stp=spanning_tree("mst"))

    result = render(config)
    lines = result.payload.splitlines()
    spans = {tuple(span.path): (span.start, span.end) for span in result.metadata.spans}

    assert spans[("stp", "config", "core")] == (1, 2)
    start, end = spans[("system", "config")]
    assert start <= lines.index("hostname sw1") + 1 <= end


def test_the_default_mode_has_no_span_of_its_own():
    result = render(ComposedConfiguration(system=System(config=SystemConfig(hostname="sw1"))))

    assert all(span.path[0] != "stp" for span in result.metadata.spans)
    assert all(span.start > 3 for span in result.metadata.spans)


def test_the_timezone_is_written_in_upper_case():
    lines = render(ComposedConfiguration(system=clock("cet 1"))).payload.splitlines()

    assert "clock timezone CET 1" in lines


@pytest.mark.parametrize("system", [System(), clock(None)])
def test_no_timezone_no_line(system):
    lines = render(ComposedConfiguration(system=system)).payload.splitlines()

    assert not [line for line in lines if line.startswith("clock")]


@pytest.mark.parametrize(
    ("on_the_device", "in_the_model"),
    [
        ("clock timezone CET 1 0", "CET 1"),  # IOS adds the minutes
        ("clock timezone CET 1", "CET 1"),
        ("clock timezone IST 5 30", "IST 5 30"),  # but a real offset in minutes stays
        ("clock timezone UTC 0 0", "UTC 0"),
        ("clock timezone EST -5 0", "EST -5"),
        ("clock timezone AEST 10", "AEST 10"),  # a zero at the end of the hours is not zero minutes
        ("clock timezone AEST 10 0", "AEST 10"),
    ],
)
def test_the_timezone_is_read_back_without_zero_minutes(on_the_device, in_the_model):
    parsed = CODEC.parse(on_the_device, None).configuration

    assert parsed.system.clock.config.timezone.value == in_the_model


def test_what_is_written_reads_back_the_same():
    written = render(ComposedConfiguration(system=clock("cet 1"))).payload

    assert CODEC.parse(written, None).configuration.system.clock.config.timezone.value == "CET 1"


def test_the_spanning_tree_lines_are_written_but_not_read_back():
    written = render(ComposedConfiguration(stp=spanning_tree("mst"))).payload

    parsed = CODEC.parse(written, None)

    assert not parsed.configuration.stp.config
    assert {unmatched.line for unmatched in parsed.metadata.unmatched} >= {
        "spanning-tree mode mst",
        "spanning-tree extend system-id",
    }
