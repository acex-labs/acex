"""
What the Junos transport raises when a session cannot be opened.

Netmiko raises its timeout error for a refused connection and for an SSH negotiation that fails, and keeps what it
caught as the context of the error. The collection agent sorts a failed node by the type of the error its driver
raises, so the transport has to tell those apart. Only netmiko's connection is replaced: the real transport runs.
"""

import asyncio
import socket

import pytest
from acex_devkit.exceptions import (
    AuthenticationFailed,
    ConnectionTimeout,
    HostUnreachable,
    SshAlgorithmMismatch,
)
from acex_devkit.models.credential import CredentialSecret
from acex_driver_juniper_junos_cli import junos_cli
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException
from paramiko.ssh_exception import SSHException

LOGIN = CredentialSecret(id=1, credential_type="userpass", fields={"username": "admin", "password": "pw"})


def netmiko_raising(error_class, caught=None):
    """A `ConnectHandler` that raises `error_class` while handling `caught`, the way netmiko does."""

    def connect(**kwargs):
        if caught is None:
            raise error_class("netmiko's own text")
        try:
            raise caught
        except Exception as reason:
            raise error_class("netmiko's own text") from reason

    return connect


def open_failing_with(monkeypatch, error_class, caught=None):
    monkeypatch.setattr(junos_cli, "ConnectHandler", netmiko_raising(error_class, caught))
    asyncio.run(junos_cli.JunosCLITransport("10.0.0.1", [LOGIN]).open())


@pytest.mark.parametrize(
    ("error_class", "caught", "raised"),
    [
        (NetmikoAuthenticationException, None, AuthenticationFailed),
        (NetmikoTimeoutException, None, ConnectionTimeout),
        (NetmikoTimeoutException, TimeoutError("timed out"), ConnectionTimeout),
        (NetmikoTimeoutException, ConnectionRefusedError(61, "Connection refused"), HostUnreachable),
        (NetmikoTimeoutException, OSError(113, "No route to host"), HostUnreachable),
        (NetmikoTimeoutException, socket.gaierror(-2, "Name or service not known"), HostUnreachable),
        (
            NetmikoTimeoutException,
            SSHException("Incompatible ssh peer (no acceptable kex algorithm)"),
            SshAlgorithmMismatch,
        ),
        (
            NetmikoTimeoutException,
            SSHException("Incompatible ssh server (no acceptable ciphers)"),
            SshAlgorithmMismatch,
        ),
        (NetmikoTimeoutException, SSHException("Incompatible ssh server (no acceptable macs)"), SshAlgorithmMismatch),
        (NetmikoTimeoutException, SSHException("Error reading SSH protocol banner"), ConnectionTimeout),
    ],
    ids=[
        "authentication",
        "no context",
        "socket timeout",
        "refused",
        "no route",
        "dns",
        "kex",
        "ciphers",
        "macs",
        "other ssh error",
    ],
)
def test_an_error_while_opening_is_raised_as_the_devkit_error_for_it(monkeypatch, error_class, caught, raised):
    with pytest.raises(raised) as caught_error:
        open_failing_with(monkeypatch, error_class, caught)

    assert type(caught_error.value) is raised


def test_the_reason_the_device_gave_is_kept_in_the_message(monkeypatch):
    with pytest.raises(SshAlgorithmMismatch, match="no acceptable kex algorithm"):
        open_failing_with(
            monkeypatch, NetmikoTimeoutException, SSHException("Incompatible ssh peer (no acceptable kex algorithm)")
        )

    with pytest.raises(HostUnreachable, match="Connection refused"):
        open_failing_with(monkeypatch, NetmikoTimeoutException, ConnectionRefusedError(61, "Connection refused"))


def test_an_error_nobody_expected_is_not_hidden(monkeypatch):
    def connect(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(junos_cli, "ConnectHandler", connect)

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(junos_cli.JunosCLITransport("10.0.0.1", [LOGIN]).open())
