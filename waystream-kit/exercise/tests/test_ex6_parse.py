import json

import pytest
from acex_driver_waystream_ibos.codec import IbosCodec
from ibos_helpers import view

from ibos_kit.accounting import expected_unmatched, unaccounted
from ibos_kit.paths import DEVICE_FIXTURES, GOLDEN, VARIANTS

CASES = ["asr6000-6.3.5", "ms4000-6.3.5"]


def parse(raw: str):
    return IbosCodec().parse(raw, None)


@pytest.mark.parametrize("name", CASES)
def test_hostname_and_the_interfaces_come_out_as_the_golden_file_says(name):
    golden = json.loads((GOLDEN / f"{name}.parsed.json").read_text())
    parsed = view(parse((GOLDEN / golden["from"]).read_text()))
    assert parsed["hostname"] == golden["hostname"]
    assert parsed["interfaces"] == golden["interfaces"]


@pytest.mark.parametrize("name", CASES)
def test_everything_this_parser_does_not_model_stays_visible_as_unmatched(name):
    golden = json.loads((GOLDEN / f"{name}.parsed.json").read_text())
    text = (GOLDEN / golden["from"]).read_text()
    unmatched = view(parse(text))["unmatched"]
    assert sorted(unmatched) == sorted(expected_unmatched(text))
    for entry in golden["must_be_unmatched"]:
        assert (entry["line"], tuple(entry["parents"])) in unmatched


def test_a_raw_configuration_with_volatile_lines_parses_like_the_one_without():
    raw = (DEVICE_FIXTURES / "ms4000-6.3.5/running-config.with-client.txt").read_text()
    clean = (DEVICE_FIXTURES / "ms4000-6.3.5/running-config.txt").read_text()
    assert view(parse(raw)) == view(parse(clean))
    assert not any("!volatile" in line for line, _ in view(parse(raw))["unmatched"])


def test_a_port_without_a_no_shutdown_line_is_disabled_because_shutdown_is_the_default_state():
    interfaces = view(parse((GOLDEN / "ms4000-6.3.5.normalized.txt").read_text()))["interfaces"]
    assert interfaces["tengigabitethernet1"]["enabled"] is False
    assert interfaces["gigabitethernet21"]["enabled"] is True


@pytest.mark.parametrize("name", ["bang-separators.txt", "doc-indentation-artifacts.txt"])
def test_irregular_layouts_do_not_crash_the_parser_and_lose_no_line(name):
    text = (VARIANTS / name).read_text()
    parsed = view(parse(text))
    assert parsed["hostname"] == "ms-lab-01"
    assert unaccounted(IbosCodec().normalize(text), [line for line, _ in parsed["unmatched"]]) == []


def test_unknown_top_level_stanzas_are_kept_with_their_children():
    parsed = view(parse("hostname h\nfuture-feature one\n option a\n option b\n"))
    assert parsed["hostname"] == "h"
    assert [line for line, _ in parsed["unmatched"]] == ["future-feature one", " option a", " option b"]


def test_an_empty_configuration_parses_to_nothing_instead_of_failing():
    parsed = view(parse(""))
    assert parsed["hostname"] is None and parsed["interfaces"] == {} and parsed["unmatched"] == []
