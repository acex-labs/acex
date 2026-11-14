import re

import pytest

from ibos_kit.mock.engine import Session
from ibos_kit.mock.scenarios import device_for

pytestmark = pytest.mark.experimental

SAVED = re.compile(r"^Wrote \d+ bytes compressed configuration \(\d+ bytes uncompressed\)$")


def session(key: str = "b") -> Session:
    s = Session(device_for(key, experimental_config_mode=True))
    s.handle("enable")
    return s


def interface_block(config: str, name: str) -> list[str]:
    return config.split(f"interface {name}\n")[1].split("\n\n")[0].splitlines()


def test_the_profile_announces_itself_in_the_greeting():
    assert "EXPERIMENTAL" in Session(device_for("b", experimental_config_mode=True)).greeting()


def test_entering_configuration_mode_is_documented_and_the_error_answers_are_not():
    s = session()
    s.handle("configure terminal")
    assert s.trace[-1].level == "VERIFIED" and not s.trace[-1].assumed
    assert "CONFIG-MODE-ENTRY" in s.trace[-1].facts
    s.handle("nonsense here")
    assert s.trace[-1].level == "INFERRED" and s.trace[-1].assumed


def test_the_prompt_names_the_context_the_way_the_manual_does():
    s = session()
    s.handle("configure terminal")
    assert s.prompt == "ms-lab-01(config)#"
    for interface, context in [
        ("gigabitethernet21", "ge"),
        ("tengigabitethernet1", "te"),
        ("loopback0", "lo"),
        ("vlan2", "vlan"),
        ("downstream0", "downstream"),
        ("ethernet1/1", "eth"),
    ]:
        s.handle(f"interface {interface}")
        assert s.prompt == f"ms-lab-01(config-if-{context})#", interface
        s.handle("exit")
        assert s.prompt == "ms-lab-01(config)#"


def test_configuration_mode_changes_hostname_description_and_shutdown_and_leaves_it_again():
    s = session()
    s.handle("configure terminal")
    s.handle("interface gigabitethernet21")
    s.handle("description Customer Interface 21")
    s.handle("shutdown")
    s.handle("exit")
    s.handle("hostname ms-lab-09")
    assert s.prompt == "ms-lab-09(config)#"
    s.handle("end")
    assert s.prompt == "ms-lab-09#"
    config = s.handle("show running-config").text
    assert "hostname ms-lab-09" in config
    block = interface_block(config, "gigabitethernet21")
    assert " description Customer Interface 21" in block
    assert " no shutdown" not in block and " shutdown" not in block


def test_no_shutdown_adds_the_line_and_shutdown_takes_it_away_because_shutdown_is_the_default():
    s = session()
    s.handle("configure terminal")
    s.handle("interface tengigabitethernet1")
    s.handle("no shutdown")
    s.handle("no shutdown")
    s.handle("end")
    assert interface_block(s.handle("show running-config").text, "tengigabitethernet1").count(" no shutdown") == 1


def test_a_hostname_the_manual_does_not_allow_is_refused_with_the_error_layout():
    s = session()
    s.handle("configure terminal")
    out = s.handle("hostname bad_name").text
    assert out == "%-ERR: hostname bad_name\n" + " " * (7 + 9) + "^" * 8 + " Invalid command"
    assert s.prompt == "ms-lab-01(config)#"
    assert "HOSTNAME-RULES" in s.trace[-1].facts


def test_write_memory_answers_in_the_documented_shape_from_admin_mode_and_through_do_from_configuration_mode():
    s = session()
    assert SAVED.match(s.handle("write memory").text)
    assert SAVED.match(s.handle("write").text)
    s.handle("configure terminal")
    assert s.handle("write memory").text.startswith("%-ERR:")
    assert SAVED.match(s.handle("do write memory").text)
    assert s.trace[-1].level == "VERIFIED"


def test_do_runs_an_exec_command_from_configuration_mode():
    s = session()
    s.handle("configure terminal")
    assert s.handle("do show running-config").text.startswith("! version ibos-ms4k-6.3.5-ED-R")
    assert s.prompt == "ms-lab-01(config)#"
    assert s.handle("do enable").text.startswith("%-ERR:")


def test_the_ms7048_uses_ethernet_ports_in_configuration_mode_too():
    s = session("e")
    s.handle("configure terminal")
    s.handle("interface ethernet1/2")
    assert s.prompt == "ms-lab-05(config-if-eth)#"
    s.handle("description Changed")
    s.handle("end")
    assert " description Changed" in s.handle("show running-config").text.splitlines()


def test_the_experimental_flag_is_off_unless_asked_for():
    assert device_for("b").experimental_config_mode is False


def test_unknown_lines_in_configuration_mode_get_the_same_error_layout():
    s = session()
    s.handle("configure terminal")
    assert s.handle("nonsense here").text.startswith("%-ERR: nonsense here")
