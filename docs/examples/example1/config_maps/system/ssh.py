from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.ssh import SshServer, AuthorizedKey


class SSHConfig(ConfigMap):
    def compile(self, context):

        ssh = SshServer(
            name='ssh_config',
            enable=True,
            protocol_version=2,
            timeout=60,
            auth_retries=2
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