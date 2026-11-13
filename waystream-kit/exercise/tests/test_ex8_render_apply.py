import pytest
from acex_devkit.exceptions import ConfigurationError
from acex_devkit.models.attribute_value import AttributeValue
from acex_driver_waystream_ibos.codec import IbosCodec
from acex_driver_waystream_ibos.transport import IbosTransport
from ibos_helpers import USERPASS, opened, view

from ibos_kit.paths import GOLDEN


def parsed_golden():
    return IbosCodec().parse((GOLDEN / "ms4000-6.3.5.normalized.txt").read_text(), None)


def test_render_writes_the_modelled_lines_with_one_space_of_indentation():
    result = parsed_golden()
    result.configuration.system.config.hostname = AttributeValue(value="ms-lab-09")
    payload = IbosCodec().render(result.configuration, None).payload
    lines = payload.splitlines()
    assert "hostname ms-lab-09" in lines
    assert lines.index("hostname ms-lab-09") > lines.index("interface gigabitethernet21")  # RUNCFG-ORDER
    block = lines[lines.index("interface gigabitethernet21") + 1 :]
    assert block[0] == " description Customer Interface"
    assert " no shutdown" in block[:3]


def test_what_render_writes_parses_back_to_the_same_model():
    first = parsed_golden()
    payload = IbosCodec().render(first.configuration, None).payload
    again = IbosCodec().parse(payload, None)
    assert {k: v for k, v in view(again).items() if k != "unmatched"} == {
        k: v for k, v in view(first).items() if k != "unmatched"
    }
    assert view(again)["unmatched"] == []


async def test_apply_refuses_to_write_while_configuration_mode_is_unverified(mock):
    async with mock("b"), opened([USERPASS]) as transport:
        with pytest.raises(ConfigurationError, match="not verified"):
            await transport.apply("hostname ms-lab-09\n")


async def test_a_device_without_configuration_mode_answers_with_an_error_that_is_raised(mock, monkeypatch):
    monkeypatch.setattr(IbosTransport, "allow_unverified_config_mode", True)
    async with mock("b"), opened([USERPASS]) as transport:
        with pytest.raises(ConfigurationError, match="Invalid command"):
            await transport.apply("hostname ms-lab-09\n")


@pytest.mark.experimental
async def test_apply_enters_configuration_mode_leaves_submodes_and_ends(mock, monkeypatch):
    monkeypatch.setattr(IbosTransport, "allow_unverified_config_mode", True)
    async with mock("b", experimental_config_mode=True) as running, opened([USERPASS]) as transport:
        await transport.apply("interface gigabitethernet21\n description Changed\nhostname ms-lab-09\n")
        assert running.sessions[0].prompt == "ms-lab-09#"
        config = await transport.get_config()
    assert "hostname ms-lab-09" in config.splitlines()
    assert " description Changed" in config.splitlines()


@pytest.mark.experimental
async def test_a_rejected_line_is_raised_and_the_session_is_left_in_exec_mode(mock, monkeypatch):
    monkeypatch.setattr(IbosTransport, "allow_unverified_config_mode", True)
    async with mock("b", experimental_config_mode=True) as running, opened([USERPASS]) as transport:
        with pytest.raises(ConfigurationError, match="nonsense"):
            await transport.apply("hostname ms-lab-09\nnonsense here\n")
        assert running.sessions[0].prompt.endswith("#") and "(config" not in running.sessions[0].prompt
