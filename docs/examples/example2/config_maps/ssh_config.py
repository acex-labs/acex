from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.augments.cisco import CiscoSshDhMinSize
from acex.configuration.components.system.ssh import SshServer
from acex.configuration.components.interfaces import Svi
from acex.configuration.components.network_instances import Vlan

class SetSSHDhMinSize(ConfigMap):
    def compile(self, context):
        dh_min_size = CiscoSshDhMinSize(
            dh_min_size=2048
        )

        context.configuration.add(dh_min_size)

        vlan = Vlan(
            name = 'vlan_123',
            vlan_id = 123, 
            vlan_name = 'Mgmt'
        )
        context.configuration.add(vlan)
        
        # Below is the mgmt vlan SVI
        mgmt_svi = Svi(
            name=f'vlan123_svi', 
            vlan=vlan,
            index=0,
            description='Mgmt',
        )
        context.configuration.add(mgmt_svi)

        ssh_server = SshServer(
            enable=True,
            protocol_version=2,
            source_interface=mgmt_svi,
        )
        context.configuration.add(ssh_server)

dh_min_size = SetSSHDhMinSize()
dh_min_size.filters = FilterAttribute("role").eq("/.*/")