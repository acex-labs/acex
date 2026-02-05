from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.acl import (
    Ipv4Acl,
    Ipv6Acl,
    Ipv4AclEntry,
    Ipv6AclEntry
)

class Ipv4AclConfig(ConfigMap):
    def compile(self, context):
        ipv4_acl = Ipv4Acl(
            name = 'ipv4_acl_test',
        )

        context.configuration.add(ipv4_acl)

        ipv4aclentry1 = Ipv4AclEntry(
            name = 'ipv4aclentry1',
            sequence_id = 10,
            description = 'Permit Ipv4 traffic',
            source_address = '172.16.1.0/24',
            destination_address = '192.168.1.0/24',
            protocol = 'tcp',
            destination_port = '443',
            ipv4_acl = ipv4_acl,
        )

        context.configuration.add(ipv4aclentry1)

        ipv4aclentry2 = Ipv4AclEntry(
            name = 'ipv4aclentry2',
            sequence_id = 20,
            description = 'Permit Ipv4 traffic',
            source_address = '172.16.1.0/24',
            destination_address = '192.168.1.0/24',
            protocol = 'tcp',
            destination_port = '80',
            ipv4_acl = ipv4_acl,
        )

        context.configuration.add(ipv4aclentry2)

class Ipv6AclConfig(ConfigMap):
    def compile(self, context):
        ipv6_acl = Ipv6Acl(
            name = 'ipv6_acl_test',
        )

        context.configuration.add(ipv6_acl)

        ipv6aclentry1 = Ipv6AclEntry(
            name = 'ipv6aclentry1',
            sequence_id = 10,
            description = 'Permit Ipv6 traffic',
            source_address = '2001:db8:1::/64',
            destination_address = '2001:db8:2::/64',
            protocol = 'tcp',
            destination_port = '443',
            ipv6_acl = ipv6_acl,
        )

        context.configuration.add(ipv6aclentry1)

        ipv6aclentry2 = Ipv6AclEntry(
            name = 'ipv6aclentry2',
            sequence_id = 20,
            description = 'Permit Ipv6 traffic',
            source_address = '5000:db8:1::/64',
            destination_address = '5000:db8:2::/64',
            protocol = 'tcp',
            destination_port = '80',
            ipv6_acl = ipv6_acl,
        )

        context.configuration.add(ipv6aclentry2)

ipv4_acl_config = Ipv4AclConfig()
ipv4_acl_config.filters = FilterAttribute("site").eq("/.*/")

ipv6_acl_config = Ipv6AclConfig()
ipv6_acl_config.filters = FilterAttribute("site").eq("/.*/")