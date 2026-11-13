import pytest

from ibos_kit.mock.engine import Session
from ibos_kit.mock.scenarios import device_for

pytestmark = pytest.mark.experimental


def session() -> Session:
    return Session(device_for("b", experimental_config_mode=True))


def test_the_profile_announces_itself_in_the_greeting_and_in_every_trace_entry():
    s = session()
    assert "EXPERIMENTAL" in s.greeting()
    s.handle("configure terminal")
    assert s.trace[-1].level == "UNKNOWN" and s.trace[-1].assumed
    assert "CONFIG-MODE-ENTRY" in s.trace[-1].facts


def test_configuration_mode_changes_hostname_description_and_shutdown_and_leaves_it_again():
    s = session()
    s.handle("configure terminal")
    assert s.prompt == "ms-lab-01(config)#"
    s.handle("interface gigabitethernet21")
    assert s.prompt == "ms-lab-01(config-if)#"
    s.handle("description Customer Interface 21")
    s.handle("shutdown")
    s.handle("exit")
    s.handle("hostname ms-lab-09")
    assert s.prompt == "ms-lab-09(config)#"
    s.handle("end")
    assert s.prompt == "ms-lab-09#"
    config = s.handle("show running-config").text
    assert "hostname ms-lab-09" in config
    block = config.split("interface gigabitethernet21\n")[1].split("\n\n")[0]
    assert " description Customer Interface 21" in block.splitlines()
    assert " shutdown" in block.splitlines() and " no shutdown" not in block.splitlines()


def test_the_experimental_flag_is_off_unless_asked_for():
    assert device_for("b").experimental_config_mode is False


def test_save_is_marked_as_simulated():
    s = session()
    s.handle("configure terminal")
    assert "EXPERIMENTAL" in s.handle("write memory").text


def test_unknown_lines_in_configuration_mode_get_the_same_error_layout():
    s = session()
    s.handle("configure terminal")
    assert s.handle("nonsense here").text.startswith("%-ERR: nonsense here")
