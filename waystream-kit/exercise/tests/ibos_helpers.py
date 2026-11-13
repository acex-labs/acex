import contextlib

from acex_devkit.models.credential import CredentialSecret
from acex_driver_waystream_ibos.transport import IbosTransport

from ibos_kit.mock.scenarios import CREDENTIALS

USERPASS = CredentialSecret(
    id=1, credential_type="userpass", fields={"username": CREDENTIALS["username"], "password": CREDENTIALS["password"]}
)
ENABLE = CredentialSecret(id=2, credential_type="privilege_escalation", fields={"password": CREDENTIALS["enable"]})
WRONG_ENABLE = CredentialSecret(id=3, credential_type="privilege_escalation", fields={"password": "not-it"})
WRONG_LOGIN = CredentialSecret(id=4, credential_type="userpass", fields={"username": "lab", "password": "not-it"})


@contextlib.asynccontextmanager
async def opened(credentials=(USERPASS,)):
    transport = IbosTransport("127.0.0.1", list(credentials))
    await transport.open()
    try:
        yield transport
    finally:
        await transport.close()


def value(attribute):
    return None if attribute is None else attribute.value


def view(result) -> dict:
    configuration = result.configuration
    interfaces = {
        value(interface.name): {
            "description": value(interface.description),
            "enabled": value(interface.enabled),
            "ipv4": value(interface.ipv4),
        }
        for interface in (configuration.interfaces or {}).values()
    }
    return {
        "hostname": value(configuration.system.config.hostname) if configuration.system.config else None,
        "interfaces": interfaces,
        "unmatched": [(u.line, tuple(u.parents)) for u in result.metadata.unmatched],
    }
