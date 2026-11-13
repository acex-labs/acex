import asyncio
import re

import asyncssh
import pytest
from scrapli.driver.generic import AsyncGenericDriver

from ibos_kit.mock.scenarios import CREDENTIALS
from ibos_kit.mock.server import RunningMock, build, ensure_loopback
from ibos_kit.paths import DEVICE_FIXTURES

PROMPT = re.compile(r"[\w.@()-]+[#>] ?$")
USER, PASSWORD = CREDENTIALS["username"], CREDENTIALS["password"]


async def connect(mock: RunningMock, password: str = PASSWORD, **options):
    return await asyncssh.connect(
        mock.host,
        mock.port,
        username=USER,
        password=password,
        known_hosts=None,
        client_keys=None,
        agent_path=None,
        config=None,
        **options,
    )


async def read_screen(process, timeout: float = 5) -> str:
    out = await asyncio.wait_for(process.stdout.readuntil(PROMPT), timeout)
    return out.replace("\r\n", "\n")


async def command(process, line: str, timeout: float = 5) -> str:
    process.stdin.write(line + "\n")
    return await read_screen(process, timeout)


async def shell(conn):
    process = await conn.create_process(term_type="vt100", term_size=(200, 24))
    await read_screen(process)
    return process


def body(screen: str, line: str) -> str:
    # What the device printed for `line`, without the echoed command and the final prompt.
    lines = screen.split("\n")
    assert lines[0].strip() == line
    return "\n".join(lines[1:-1]).rstrip("\n")


def test_the_mock_refuses_to_listen_anywhere_but_on_loopback():
    assert ensure_loopback("127.0.0.1") == "127.0.0.1"
    assert ensure_loopback("localhost") == "127.0.0.1"
    assert ensure_loopback("::1") == "::1"
    for host in ("0.0.0.0", "192.0.2.1", "::", "example.org", ""):
        with pytest.raises(ValueError, match="loopback"):
            ensure_loopback(host)


async def test_login_gives_the_prompt_of_the_profile():
    async with build("b") as mock, await connect(mock) as conn:
        process = await conn.create_process(term_type="vt100")
        assert (await read_screen(process)).endswith("ms-lab-01#")


async def test_wrong_password_is_refused():
    async with build("b") as mock:
        with pytest.raises(asyncssh.PermissionDenied):
            await connect(mock, password="not-the-password")


async def test_rejecting_all_logins_is_a_fault_a_driver_must_report():
    async with build("b", reject_logins=True) as mock:
        with pytest.raises(asyncssh.PermissionDenied):
            await connect(mock)


async def test_show_running_config_over_ssh_returns_the_fixture_between_echo_and_prompt():
    async with build("c") as mock, await connect(mock) as conn:
        process = await shell(conn)
        screen = await command(process, "show running-config")
        expected = (DEVICE_FIXTURES / "ms4000-6.3.5/running-config.with-client.txt").read_text().rstrip("\n")
        assert body(screen, "show running-config") == expected


async def test_user_mode_enable_and_hidden_password_over_ssh():
    async with build("d") as mock, await connect(mock) as conn:
        process = await shell(conn)
        process.stdin.write("enable\n")
        asked = await asyncio.wait_for(process.stdout.readuntil("Password:"), 5)
        assert asked.endswith("Password:")
        process.stdin.write(CREDENTIALS["enable"] + "\n")
        screen = await read_screen(process)
        assert CREDENTIALS["enable"] not in screen
        assert screen.endswith("ms-lab-04#")


async def test_a_wrong_enable_password_leaves_the_session_in_user_mode():
    async with build("d") as mock, await connect(mock) as conn:
        process = await shell(conn)
        process.stdin.write("enable\n")
        await process.stdout.readuntil("Password:")
        process.stdin.write("nope\n")
        screen = await read_screen(process)
        assert screen.endswith("ms-lab-04>")


async def test_the_reported_error_layout_survives_a_real_pty():
    async with build("e") as mock, await connect(mock) as conn:
        process = await shell(conn)
        screen = await command(process, "show running-config")
        expected = "%-ERR: show running-config\n" + " " * 12 + "^" * 14 + " Invalid command"
        assert body(screen, "show running-config") == expected


async def test_a_command_that_never_answers_times_out_on_the_client_side():
    async with build("b", hang_on=("show version",)) as mock, await connect(mock) as conn:
        process = await shell(conn)
        process.stdin.write("show version\n")
        with pytest.raises(TimeoutError):
            await read_screen(process, timeout=0.5)


async def test_a_connection_that_drops_in_the_middle_of_the_output_ends_without_a_prompt():
    async with build("b", drop_after_lines=4) as mock, await connect(mock) as conn:
        process = await shell(conn)
        process.stdin.write("show running-config\n")
        with pytest.raises(asyncio.IncompleteReadError):
            await asyncio.wait_for(process.stdout.readuntil(PROMPT), 5)


async def test_a_device_that_speaks_only_an_old_key_exchange_needs_a_client_that_does_too():
    async with build("b", legacy_kex_only=True) as mock:
        with pytest.raises(asyncssh.KeyExchangeFailed):
            await connect(mock, kex_algs=["curve25519-sha256"])
        async with await connect(mock, kex_algs=["diffie-hellman-group14-sha1"]) as conn:
            process = await conn.create_process(term_type="vt100")
            assert (await read_screen(process)).endswith("ms-lab-01#")


async def test_latency_delays_every_answer():
    async with build("b", latency_ms=300) as mock, await connect(mock) as conn:
        process = await shell(conn)
        started = asyncio.get_running_loop().time()
        await command(process, "show vlan")
        assert asyncio.get_running_loop().time() - started >= 0.3


async def test_every_command_is_traced_with_the_evidence_it_rests_on():
    async with build("b") as mock, await connect(mock) as conn:
        process = await shell(conn)
        await command(process, "show version")
        await command(process, "show nonsense")
        trace = mock.sessions[0].trace
        assert [t.command for t in trace] == ["show version", "show nonsense"]
        assert trace[1].facts == ("ERROR-FORMAT",)


async def test_a_generic_scrapli_client_can_read_the_configuration_of_scenario_b():
    async with build("b") as mock:
        client = AsyncGenericDriver(
            host=mock.host,
            port=mock.port,
            auth_username=USER,
            auth_password=PASSWORD,
            auth_strict_key=False,
            transport="asyncssh",
            ssh_config_file=False,
            ssh_known_hosts_file=False,
            timeout_socket=5,
            timeout_ops=5,
            comms_prompt_pattern=r"^[\w.@()-]+[#>]\s?$",
        )
        async with client:
            await client.send_command("terminal no pager")
            result = await client.send_command("show running-config")
        assert result.result == (DEVICE_FIXTURES / "ms4000-6.3.5/running-config.txt").read_text().rstrip("\n")


async def test_the_mock_shuts_down_even_when_a_client_forgets_to_disconnect():
    async with build("b") as mock:
        conn = await connect(mock)
        assert len(mock.connections) == 1
    await asyncio.wait_for(conn.wait_closed(), 5)
    assert not mock.connections


async def test_a_client_without_a_terminal_still_gets_answers_and_the_hidden_password_does_not_kill_the_session():
    async with build("d") as mock, await connect(mock) as conn:
        process = await conn.create_process()
        process.stdin.write("enable\n")
        await asyncio.wait_for(process.stdout.readuntil("Password:"), 5)
        process.stdin.write(CREDENTIALS["enable"] + "\n")
        await asyncio.wait_for(process.stdout.readuntil("ms-lab-04#"), 5)
        process.stdin.write("show vlan\n")
        screen = await asyncio.wait_for(process.stdout.readuntil("ms-lab-04#"), 5)
        assert "tengigabitethernet1" in screen
