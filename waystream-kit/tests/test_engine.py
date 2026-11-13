import re

import pytest

from ibos_kit import evidence
from ibos_kit.mock.engine import Session
from ibos_kit.mock.scenarios import SCENARIOS, device_for
from ibos_kit.paths import DEVICE_FIXTURES

OXIDIZED_PROMPT = re.compile(r"^([\w.@()-]+[#>]\s?)$")


def fixture(path: str) -> str:
    return (DEVICE_FIXTURES / path).read_text().rstrip("\n")


def open_session(key: str, **overrides) -> Session:
    return Session(device_for(key, **overrides))


def run(session: Session, line: str) -> str:
    return session.handle(line).text


def test_every_scenario_from_the_brief_exists_and_can_be_looked_up_by_its_letter():
    assert set("abcdef") <= {key[0] for key in SCENARIOS}
    for letter in "abcdef":
        assert device_for(letter).profile.hostname


@pytest.mark.parametrize(
    ("key", "prompt"),
    [
        ("a", "asr-lab-01#"),
        ("b", "ms-lab-01#"),
        ("c", "ms-lab-01#"),
        ("d", "ms-lab-04>"),
        ("e", "ms-lab-05>"),
    ],
)
def test_the_session_lands_in_the_mode_of_the_profile_and_the_prompt_is_one_the_third_party_driver_accepts(key, prompt):
    session = open_session(key)
    assert session.prompt == prompt
    assert OXIDIZED_PROMPT.match(session.prompt)
    assert session.greeting().endswith(prompt)


def test_a_trailing_space_after_the_prompt_is_available_for_rehearsal():
    session = open_session("b", prompt_trailing_space=True)
    assert session.prompt == "ms-lab-01# "
    assert OXIDIZED_PROMPT.match(session.prompt)


def test_show_running_config_prints_the_fixture_of_the_scenario():
    assert run(open_session("a"), "show running-config") == fixture("asr6000-6.3.5/running-config.txt")
    assert run(open_session("b"), "show running-config") == fixture("ms4000-6.3.5/running-config.txt")


def test_scenario_c_has_volatile_lines_where_b_has_none():
    assert "!volatile" not in run(open_session("b"), "show running-config")
    config = run(open_session("c"), "show running-config")
    assert re.search(r"^ !volatile policy-map vid 2 snpa \S+ \S+/32 seq 10 policy$", config, re.MULTILINE)


def test_the_context_form_prints_one_interface_block_with_the_version_comment():
    out = run(open_session("c"), "show running-configuration context interface gigabitethernet21")
    assert out == fixture("ms4000-6.3.5/show-running-configuration-context-interface-gigabitethernet21.txt")
    assert out.splitlines()[0].startswith("! version ibos-ms4k-6.3.5-ED-R")


def test_the_documented_abbreviations_work_and_others_are_not_invented():
    assert run(open_session("b"), "sh vlan") == run(open_session("b"), "show vlan")
    assert run(open_session("a"), "sh ip int br") == fixture("asr6000-6.3.5/show-ip-interface-brief.txt")
    assert run(open_session("b"), "sh ru").startswith("%-ERR:")


def test_unknown_commands_get_the_error_layout_of_the_one_report_we_have():
    out = run(open_session("b"), "show nonsense")
    assert out == "%-ERR: show nonsense\n" + " " * 12 + "^" * 8 + " Invalid command"
    assert run(open_session("b"), "foo") == "%-ERR: foo\n" + " " * 7 + "^^^ Invalid command"
    assert run(open_session("b"), "show version extra").splitlines()[1] == " " * (7 + 13) + "^^^^^ Invalid command"


def test_ms7048_rejects_show_running_config_in_user_mode_exactly_as_reported():
    session = open_session("e")
    assert run(session, "show running-config") == (
        "%-ERR: show running-config\n" + " " * 12 + "^" * 14 + " Invalid command"
    )


def test_ms7048_accepts_it_after_enable_in_the_default_scenario_and_never_in_the_hard_one():
    session = open_session("e")
    assert run(session, "enable") == ""
    assert session.prompt == "ms-lab-05#"
    assert run(session, "show running-config").startswith("! version ibos-cma-7.6.2-GD-R")

    hard = Session(device_for("e-ms7048-762-never"))
    run(hard, "enable")
    assert run(hard, "show running-config").startswith("%-ERR: show running-config")


def test_enable_asks_for_a_password_when_one_is_set_and_hides_the_typing():
    session = open_session("d")
    reply = session.handle("enable")
    assert reply.text == "Password:"
    assert reply.echo is False
    assert reply.prompt_follows is False
    bad = session.handle("wrong")
    assert session.prompt == "ms-lab-04>"
    assert bad.echo is True
    session.handle("enable")
    good = session.handle("lab-enable-not-secret")
    assert good.text == "" and session.prompt == "ms-lab-04#"


def test_the_read_only_commands_of_the_installation_guide_work_on_the_630_profile():
    session = open_session("d")
    assert run(session, "show version") == fixture("ms4000-6.3.0/show-version.txt")
    assert run(session, "show vlan") == fixture("ms4000-6.3.0/show-vlan.txt")
    assert run(session, "show pfdp neighbours") == fixture("ms4000-6.3.0/show-pfdp-neighbours.txt")
    assert run(session, "show running-config").startswith("%-ERR:")


def test_terminal_commands_are_accepted_silently():
    session = open_session("b")
    assert run(session, "terminal no pager") == ""
    assert run(session, "terminal width 65535") == ""


def test_exit_closes_the_session():
    assert open_session("b").handle("exit").close is True


def test_blank_input_just_gives_a_new_prompt():
    assert run(open_session("b"), "") == ""


def test_output_is_deterministic_and_has_no_carriage_returns_or_trailing_spaces():
    for letter in "abcde":
        first, second = open_session(letter), open_session(letter)
        for command in ("show version", "show vlan"):
            out = run(first, command)
            assert out == run(second, command)
            assert "\r" not in out


def test_configuration_mode_does_not_exist_unless_asked_for():
    session = open_session("b")
    out = run(session, "configure terminal")
    assert out == "%-ERR: configure terminal\n" + " " * 7 + "^" * 9 + " Invalid command"
    assert session.prompt == "ms-lab-01#"
    assert run(session, "hostname other").startswith("%-ERR:")


def test_faults_are_reported_to_the_server_layer():
    hang = open_session("b", hang_on=("show running-config",)).handle("show running-config")
    assert hang.hang is True
    drop = open_session("b", drop_after_lines=4).handle("show running-config")
    assert drop.drop is True and len(drop.text.splitlines()) == 4


def test_every_answer_is_traced_with_the_facts_it_rests_on_and_the_worst_level():
    session = open_session("b")
    session.handle("show version")
    session.handle("show running-config")
    session.handle("show nonsense")
    version, config, error = session.trace
    assert version.command == "show version" and "SHOW-VERSION-MS4K-635" in version.facts
    assert version.level == "INFERRED" and version.assumed
    assert config.level == "UNKNOWN"  # the block separator is not known, and the answer assumes one
    assert error.facts == ("ERROR-FORMAT",)


def test_every_fact_the_mock_cites_exists_in_the_register():
    register = evidence.load()
    cited = set()
    for key in SCENARIOS:
        device = device_for(key)
        for command in device.profile.commands:
            cited.update(command.facts)
    cited.update({"PROMPT-MODES", "ERROR-FORMAT", "ENABLE-COMMAND", "TERMINAL-COMMANDS", "COMMAND-ABBREVIATION"})
    assert cited <= set(register.facts), cited - set(register.facts)


def test_experimental_flag_adds_a_visible_marker_to_the_greeting():
    session = open_session("b", experimental_config_mode=True)
    assert "EXPERIMENTAL" in session.greeting()
