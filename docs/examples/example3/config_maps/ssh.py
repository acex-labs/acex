from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.ssh import SshServer, AuthorizedKey
from acex.configuration.components.interfaces import Loopback


class SSHConfig(ConfigMap):
    def compile(self, context):

        lo = Loopback(
            name="My_loopback",
            index=0
        )
        context.configuration.add(lo)

        ssh = SshServer(
            name='ssh_config',
            enable=True,
            protocol_version=2,
            timeout=60,
            auth_retries=2,
            # source_interface="Lo0"
            source_interface=lo
        )
        context.configuration.add(ssh)

        ssh_key = AuthorizedKey(
            name="my_key",
            algorithm="ssh-ed25519",
            public_key="ssh-ed25519 MYSSHPUBKEYCOMESHEREBUTSHOULDBEVALID"
        )
        context.configuration.add(ssh_key)

sshconfig = SSHConfig()
sshconfig_filter = FilterAttribute("hostname").eq("/.*/")
sshconfig.filters = sshconfig_filter