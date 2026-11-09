from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.ssh import SshServer

from config_maps.common.mgmt_vlan import mgmt_vlan

class ConfigureSshServer_ssh_server(ConfigMap):
    def compile(self, context):
        ssh_server = SshServer(
            enable=True,
            protocol_version=2,
            source_interface=mgmt_vlan.mgmt_svi,
        )
        context.configuration.add(ssh_server)


config = ConfigureSshServer_ssh_server()
config.filters = (
    FilterAttribute("role").eq("access")
    | FilterAttribute("role").eq("distribution")
    | FilterAttribute("role").eq("core")
)
