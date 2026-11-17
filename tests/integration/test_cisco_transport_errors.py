"""
What the Cisco transports raise when a session cannot be opened.

The collection agent sorts a failed node by the type of the error its driver raises, so a transport that lets a raw
scrapli, asyncssh or socket error through leaves the node without a reason. Only the scrapli connection is replaced
here: the real transports run, one for each Cisco driver.
"""

import asyncio

import pytest
from acex_devkit.exceptions import (
    AuthenticationFailed,
    ConnectionTimeout,
    HostUnreachable,
    PrivilegeFailed,
    SshAlgorithmMismatch,
)
from acex_devkit.models.credential import CredentialSecret
from acex_driver_cisco_ios_classic_cli.transport import transport as classic
from acex_driver_cisco_ioscli.transport import transport as iosxe
from asyncssh import KeyExchangeFailed
from scrapli.exceptions import ScrapliAuthenticationFailed, ScrapliPrivilegeError, ScrapliTimeout

LOGIN = CredentialSecret(id=1, credential_type="userpass", fields={"username": "admin", "password": "pw"})


def auth_failed_by_timeout() -> ScrapliAuthenticationFailed:
    error = ScrapliAuthenticationFailed("timed out opening connection to device")
    error.__cause__ = TimeoutError()
    return error


@pytest.fixture(params=[iosxe, classic], ids=["iosxe", "ios"])
def transport_module(request):
    return request.param


def open_failing_with(module, monkeypatch, error):
    class SessionThatFails:
        def __init__(self, **kwargs):
            pass

        async def open(self):
            raise error

    monkeypatch.setattr(module, "AsyncIOSXEDriver", SessionThatFails)
    asyncio.run(module.CiscoIOSTransport("10.0.0.1", [LOGIN]).open())


@pytest.mark.parametrize(
    ("error", "raised"),
    [
        (ScrapliAuthenticationFailed("all authentication methods failed"), AuthenticationFailed),
        (auth_failed_by_timeout(), ConnectionTimeout),
        (ScrapliTimeout("timed out"), ConnectionTimeout),
        (TimeoutError("timed out"), ConnectionTimeout),
        (ScrapliPrivilegeError("Failed to acquire requested privilege level privilege_exec"), PrivilegeFailed),
        (KeyExchangeFailed("No matching key exchange algorithm found"), SshAlgorithmMismatch),
        (KeyExchangeFailed("No matching cipher algorithm found"), SshAlgorithmMismatch),
        (ConnectionRefusedError(61, "Connect call failed"), HostUnreachable),
        (OSError(113, "No route to host"), HostUnreachable),
    ],
    ids=lambda value: type(value).__name__ if isinstance(value, Exception) else value.__name__,
)
def test_an_error_while_opening_is_raised_as_the_devkit_error_for_it(transport_module, monkeypatch, error, raised):
    with pytest.raises(raised) as caught:
        open_failing_with(transport_module, monkeypatch, error)

    assert type(caught.value) is raised
    assert caught.value.__cause__ is error


@pytest.mark.parametrize(
    ("error", "said"),
    [
        (ScrapliPrivilegeError("Failed to acquire requested privilege level privilege_exec"), "privilege level"),
        (KeyExchangeFailed("No matching cipher algorithm found"), "cipher algorithm"),
        (ConnectionRefusedError(61, "Connect call failed"), "Connect call failed"),
    ],
    ids=["privilege", "algorithm", "refused"],
)
def test_the_reason_the_device_gave_is_kept_in_the_message(transport_module, monkeypatch, error, said):
    with pytest.raises(Exception, match=said):
        open_failing_with(transport_module, monkeypatch, error)


def test_an_error_nobody_expected_is_not_hidden(transport_module, monkeypatch):
    with pytest.raises(RuntimeError, match="boom"):
        open_failing_with(transport_module, monkeypatch, RuntimeError("boom"))
