from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.acl import (
    #AclEntry,
    #AclIpv4, 
    #AclIcmpv4,
    #AclTransport
    AclIpv4,
    AclIpv6,
    Ipv4AclSet,
    Ipv6AclSet
)

class Ipv4AclConfig(ConfigMap):
    def compile(self, context):
        ipv4_acl = Ipv4AclSet(
            name = 'ipv4 acl set test',
        )

        context.configuration.add(ipv4_acl)

        ipv4aclentry1 = AclIpv4(
            name = 'ipv4aclentry1',
            sequence_id = 10,
            description = 'Permit Ipv4 traffic',
            source = '172.16.1.0/24',
            destination = '192.168.1.0/24',
            protocol = 'tcp',
            destination_port = '443',
            ipv4acl_set = ipv4_acl,
        )

        context.configuration.add(ipv4aclentry1)

        ipv4aclentry2 = AclIpv4(
            name = 'ipv4aclentry2',
            sequence_id = 20,
            description = 'Permit Ipv4 traffic',
            source = '172.16.1.0/24',
            destination = '192.168.1.0/24',
            protocol = 'tcp',
            destination_port = '80',
            ipv4acl_set = ipv4_acl,
        )

        context.configuration.add(ipv4aclentry2)

class Ipv6AclConfig(ConfigMap):
    def compile(self, context):
        ipv6_acl = Ipv6AclSet(
            name = 'ipv6 acl set test',
        )

        context.configuration.add(ipv6_acl)

        ipv6aclentry1 = AclIpv6(
            name = 'ipv6aclentry1',
            sequence_id = 10,
            description = 'Permit Ipv6 traffic',
            source = '2001:db8:1::/64',
            destination = '2001:db8:2::/64',
            protocol = 'tcp',
            destination_port = '443',
            ipv6acl_set = ipv6_acl,
        )

        context.configuration.add(ipv6aclentry1)

        ipv6aclentry2 = AclIpv6(
            name = 'ipv6aclentry2',
            sequence_id = 20,
            description = 'Permit Ipv6 traffic',
            source = '5000:db8:1::/64',
            destination = '5000:db8:2::/64',
            protocol = 'tcp',
            destination_port = '80',
            ipv6acl_set = ipv6_acl,
        )

        context.configuration.add(ipv6aclentry2)

ipv4_acl_config = Ipv4AclConfig()
ipv4_acl_config.filters = FilterAttribute("site").eq("/.*/")

ipv6_acl_config = Ipv6AclConfig()
ipv6_acl_config.filters = FilterAttribute("site").eq("/.*/")