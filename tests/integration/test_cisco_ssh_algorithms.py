"""
The SSH algorithms the two Cisco transports offer, against SSH servers that only speak what older devices do.

An older device may offer only CBC ciphers, for example 3des-cbc. asyncssh leaves every CBC cipher out of its
defaults, so the transports append them (`LEGACY_ASYNCSSH_OPTIONS`) after the modern ones. The servers here are real
asyncssh servers limited to the algorithms of such a device; the client is asyncssh with the options the transport
hands to scrapli.
"""

import asyncio
from unittest.mock import patch

import asyncssh
import pytest
from acex_devkit.models.credential import CredentialSecret
from acex_driver_cisco_ios_classic_cli.transport import transport as classic_transport
from acex_driver_cisco_ioscli.transport import transport as iosxe_transport

TRANSPORT_MODULES = [classic_transport, iosxe_transport]
TRANSPORTS = [pytest.param(module, id=module.__name__.split(".")[0]) for module in TRANSPORT_MODULES]


class OpenServer(asyncssh.SSHServer):
    """Lets every client in, so only the algorithm negotiation decides whether a connection works."""

    def begin_auth(self, username):
        return False


def negotiated_cipher(server_options: dict, client_options: dict) -> str:
    async def run() -> str:
        server = await asyncssh.create_server(
            OpenServer,
            "127.0.0.1",
            0,
            server_host_keys=[asyncssh.generate_private_key("ssh-ed25519")],
            **server_options,
        )
        port = server.sockets[0].getsockname()[1]
        connect = asyncssh.connect("127.0.0.1", port, username="admin", known_hosts=None, **client_options)
        try:
            async with connect as conn:
                return conn.get_extra_info("send_cipher")
        finally:
            server.close()
            await server.wait_closed()

    return asyncio.run(run())


@pytest.mark.parametrize("cipher", ["3des-cbc", "aes128-cbc", "aes192-cbc", "aes256-cbc"])
@pytest.mark.parametrize("module", TRANSPORTS)
def test_a_device_that_only_offers_a_cbc_cipher_can_be_reached(module, cipher):
    options = module.CiscoIOSTransport.LEGACY_ASYNCSSH_OPTIONS

    assert negotiated_cipher({"encryption_algs": [cipher]}, options) == cipher


@pytest.mark.parametrize("module", TRANSPORTS)
def test_a_device_that_offers_all_the_cbc_ciphers_gets_the_strongest(module):
    offered = ["aes128-cbc", "3des-cbc", "aes192-cbc", "aes256-cbc"]

    assert negotiated_cipher({"encryption_algs": offered}, module.CiscoIOSTransport.LEGACY_ASYNCSSH_OPTIONS) == (
        "aes256-cbc"
    )


def test_without_the_legacy_options_a_3des_cbc_device_cannot_be_reached():
    with pytest.raises(asyncssh.KeyExchangeFailed, match="No matching encryption algorithm"):
        negotiated_cipher({"encryption_algs": ["3des-cbc"]}, {})


@pytest.mark.parametrize("module", TRANSPORTS)
def test_a_device_with_modern_ciphers_does_not_get_a_cbc_cipher(module):
    cipher = negotiated_cipher({}, module.CiscoIOSTransport.LEGACY_ASYNCSSH_OPTIONS)

    assert "cbc" not in cipher


@pytest.mark.parametrize("module", TRANSPORTS)
def test_the_transport_hands_the_legacy_options_to_scrapli(module):
    opened = {}

    class FakeScrapli:
        def __init__(self, **kwargs):
            opened.update(kwargs)

        async def open(self):
            pass

    credentials = [CredentialSecret(id=1, credential_type="userpass", fields={"username": "admin", "password": "pw"})]
    transport = module.CiscoIOSTransport("192.0.2.10", credentials)

    with patch.object(module, "AsyncIOSXEDriver", FakeScrapli):
        asyncio.run(transport.open())

    assert opened["transport"] == "asyncssh"
    assert opened["transport_options"] == {"asyncssh": module.CiscoIOSTransport.LEGACY_ASYNCSSH_OPTIONS}
