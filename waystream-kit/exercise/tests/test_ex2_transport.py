import asyncio
import socket

import pytest
from acex_devkit.exceptions import AuthenticationFailed, ConnectionError, ConnectionTimeout
from acex_driver_waystream_ibos.transport import IbosTransport
from ibos_helpers import ENABLE, USERPASS, WRONG_ENABLE, WRONG_LOGIN, opened

from ibos_kit.paths import DEVICE_FIXTURES


def fixture(path: str) -> str:
    return (DEVICE_FIXTURES / path).read_text().rstrip("\n")


async def test_execute_returns_one_output_per_command_without_the_echo_and_the_prompt(mock):
    async with mock("b"), opened() as transport:
        outputs = await transport.execute(["show version", "show vlan"])
    assert outputs == [fixture("ms4000-6.3.5/show-version.assumed.txt"), fixture("ms4000-6.3.5/show-vlan.txt")]


async def test_terminal_width_is_set_once_before_the_first_command(mock):
    async with mock("b") as running, opened() as transport:
        await transport.execute(["show vlan"])
    commands = [entry.command for entry in running.sessions[0].trace]
    assert commands.count("terminal width 65535") == 1
    assert commands.index("terminal width 65535") < commands.index("show vlan")


@pytest.mark.parametrize(
    ("scenario", "credentials"),
    [("a", [USERPASS]), ("b", [USERPASS]), ("c", [USERPASS]), ("d", [USERPASS, ENABLE]), ("e", [USERPASS])],
)
async def test_open_works_on_every_scenario_including_firmware_that_has_no_terminal_no_pager(
    mock, scenario, credentials
):
    async with mock(scenario) as running, opened(credentials) as transport:
        assert not (await transport.execute(["show version"]))[0].startswith("%-ERR")
    assert running.sessions[0].mode == "privileged"


async def test_a_prompt_with_a_trailing_space_works_too(mock):
    async with mock("b", prompt_trailing_space=True), opened() as transport:
        assert await transport.execute(["show vlan"]) == [fixture("ms4000-6.3.5/show-vlan.txt")]


async def test_a_device_in_user_mode_without_an_enable_password_is_enabled_on_open(mock):
    async with mock("e") as running, opened():
        assert running.sessions[0].prompt == "ms-lab-05#"


async def test_a_device_with_an_enable_password_is_enabled_with_the_privilege_escalation_credential(mock):
    async with mock("d") as running, opened([USERPASS, ENABLE]):
        assert running.sessions[0].prompt == "ms-lab-04#"


async def test_a_missing_enable_password_is_an_authentication_failure_not_a_hang(mock):
    async with mock("d"):
        with pytest.raises(AuthenticationFailed):
            async with opened([USERPASS]):
                pass


async def test_a_wrong_enable_password_is_an_authentication_failure(mock):
    async with mock("d"):
        with pytest.raises(AuthenticationFailed):
            async with opened([USERPASS, WRONG_ENABLE]):
                pass


async def test_a_wrong_login_password_is_an_authentication_failure(mock):
    async with mock("b"):
        with pytest.raises(AuthenticationFailed):
            async with opened([WRONG_LOGIN]):
                pass


async def test_a_device_that_rejects_every_login_is_an_authentication_failure(mock):
    async with mock("f", reject_logins=True):
        with pytest.raises(AuthenticationFailed):
            async with opened():
                pass


async def test_nothing_listening_is_a_connection_error(monkeypatch):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    monkeypatch.setattr(IbosTransport, "PORT", free_port)
    with pytest.raises(ConnectionError):
        async with opened():
            pass


async def test_a_command_that_never_answers_is_a_connection_timeout(mock, monkeypatch):
    monkeypatch.setattr(IbosTransport, "timeout_ops", 1)
    async with mock("f", hang_on=("show vlan",)), opened() as transport:
        with pytest.raises(ConnectionTimeout):
            await transport.execute(["show vlan"])


async def test_a_device_with_only_an_old_key_exchange_can_still_be_reached(mock):
    async with mock("f", legacy_kex_only=True), opened() as transport:
        assert await transport.execute(["show vlan"]) == [fixture("ms4000-6.3.5/show-vlan.txt")]


async def test_close_can_be_called_twice(mock):
    async with mock("b"):
        transport = IbosTransport("127.0.0.1", [USERPASS])
        await transport.open()
        await transport.close()
        await transport.close()


async def test_a_failed_open_leaves_no_connection_behind(mock):
    async with mock("d") as running:
        with pytest.raises(AuthenticationFailed):
            async with opened([USERPASS, WRONG_ENABLE]):
                pass
        await asyncio.sleep(0.2)
        assert not running.connections
