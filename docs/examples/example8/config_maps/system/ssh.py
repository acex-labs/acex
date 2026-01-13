from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.ssh import SshServer
from acex.configuration.components.vlan import Vlan
from acex.configuration.components.interfaces import Svi

class SSHConfig(ConfigMap):
    def compile(self, context):

        vl2 = Vlan(
            name="vlan_1337",
            vlan_id=1337,
            vlan_name="Mgmt"
        )
        context.configuration.add(vl2)

        svi2 = Svi(
            name='vlan1337_svi',
            description='Mgmt',
            index=1337,
            vlan=vl2
        )

        context.configuration.add(svi2)

        ssh = SshServer(
            name='ssh_config',
            enable=True,
            protocol_version=2,
            source_interface=svi2
        )
        context.configuration.add(ssh)

sshconfig = SSHConfig()
sshconfig_filter = FilterAttribute("hostname").eq("/.*/")
sshconfig.filters = sshconfig_filter