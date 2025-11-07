from acex.core.config_map import ConfigMap, FilterAttribute
from acex.core.configuration.components.system.ssh import SSHServer


class SSHConfig(ConfigMap):
    def compile(self, context):

        ssh = SSHServer(
            name='ssh_config',
            enable=True,
            protocol_version=2,
            timeout=60,
            auth_retries=2
        )
        context.configuration.add(ssh)

sshconfig = SSHConfig()
sshconfig_filter = FilterAttribute("hostname").eq("/.*/")
sshconfig.filters = sshconfig_filter